import os
import ast
import json
import re
import uuid
import subprocess
from openai import OpenAI
from dotenv import load_dotenv
from rich.console import Console
from core.logger import registrar_evento

load_dotenv()
console = Console()

TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "get_project_tree", "description": "Lista arquivos da pasta do projeto.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "default": "."}}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Lê o conteúdo de um arquivo dentro do projeto (ex: server_axel.py).", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Cria ou sobrescreve um arquivo dentro do projeto.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "run_command", "description": "Executa comandos no terminal (exige aprovação humana).", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "justificativa": {"type": "string"}}, "required": ["command", "justificativa"]}}}
]

# Padrões bloqueados por segurança (AppSec)
PASTAS_BLOQUEADAS = {".git", "venv", ".venv", "__pycache__"}
COMANDOS_PROIBIDOS = [
    r"rm\s+-rf", r"del\s+/[fqsa]", r"rd\s+/s", r"rmdir\s+/s",
    r"format\s+[a-z]:", r"shutdown", r"reg\s+delete",
    r"(type|cat|more|get-content|gc)\s+.*\.env"
]


class BionicAgent:
    def __init__(self, workspace_path: str, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        self.ollama_client = OpenAI(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key="ollama"
        )
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.history = []
        self.comandos_pendentes = {}
        self.root_dir = os.path.realpath(os.getcwd())

        # Fila de Fallback (Online Pago -> Online Gratuito -> Local Ollama)
        self.modelos_ativos = [
            os.getenv("ONLINE_MODEL", "google/gemini-2.5-flash"),
            "openrouter/free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ]

    def _atualizar_modelos(self):
        self.modelos_ativos = [
            os.getenv("ONLINE_MODEL", "google/gemini-2.5-flash"),
            "openrouter/free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ]

    def _extrair_usage(self, resp) -> dict:
        usage = getattr(resp, "usage", None)
        if not usage:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        }

    def _chamar_llm_com_fallback(self, usar_tools: bool = True):
        """Tenta os modelos em cascata; se acabar crédito/limite (402/429), troca automaticamente."""
        modo_offline = "localhost" in str(self.client.base_url)

        if modo_offline:
            candidatos = [(self.ollama_client, self.ollama_model)]
        else:
            candidatos = [(self.client, m) for m in self.modelos_ativos]
            candidatos.append((self.ollama_client, self.ollama_model))

        ultimo_erro = None
        for cliente, modelo in candidatos:
            try:
                kwargs = {
                    "model": modelo,
                    "messages": self.history,
                    "max_tokens": 1024
                }
                if usar_tools:
                    kwargs["tools"] = TOOLS_SCHEMA
                    kwargs["tool_choice"] = "auto"

                resp = cliente.chat.completions.create(**kwargs)
                return resp, modelo, self._extrair_usage(resp)
            except Exception as e:
                ultimo_erro = e
                print(f"⚠️ [FALLBACK] Modelo '{modelo}' falhou ({str(e)[:90]}...). Tentando próximo...")
                registrar_evento(
                    "llm_fallback",
                    modelo=modelo,
                    status="warn",
                    detalhes={"erro": str(e)[:180]}
                )
                continue

        raise RuntimeError(f"Todos os modelos (online e local) falharam. Último erro: {ultimo_erro}")

    def _validar_caminho_seguro(self, caminho_bruto: str):
        """Impede Path Traversal e bloqueia acesso a arquivos/pastas sensíveis."""
        if not caminho_bruto:
            return None, "Erro de Segurança: Caminho vazio."

        candidato = caminho_bruto if os.path.isabs(caminho_bruto) else os.path.join(self.root_dir, caminho_bruto)
        caminho_real = os.path.realpath(candidato)

        try:
            if os.path.commonpath([self.root_dir, caminho_real]) != self.root_dir:
                return None, "BLOQUEADO (AppSec): Acesso negado fora do diretório do projeto."
        except ValueError:
            return None, "BLOQUEADO (AppSec): Acesso negado em outra unidade de disco."

        nome_arquivo = os.path.basename(caminho_real).lower()
        partes_caminho = {p.lower() for p in os.path.relpath(caminho_real, self.root_dir).split(os.sep)}

        if nome_arquivo == ".env" or (nome_arquivo.startswith(".env.") and nome_arquivo != ".env.example"):
            return None, "BLOQUEADO (AppSec): Leitura ou escrita no arquivo .env é proibida."

        if partes_caminho.intersection(PASTAS_BLOQUEADAS):
            return None, "BLOQUEADO (AppSec): Acesso a pastas internas (.git, venv, __pycache__) é proibido."

        return caminho_real, None

    def _comando_eh_proibido(self, cmd: str) -> bool:
        cmd_lower = cmd.lower()
        return any(re.search(padrao, cmd_lower) for padrao in COMANDOS_PROIBIDOS)

    def enviar_mensagem(self, prompt: str):
        self.history.append({"role": "user", "content": prompt})

        bionic_prompt = (
            "\n\n[MOTOR BIONIC ATIVADO]: Você é um Engenheiro de IA Autônomo com permissões controladas.\n"
            f"O seu diretório atual (onde seu código mora) é: {self.root_dir}\n"
            "REGRA 1: Execute as ferramentas IMEDIATAMENTE. Não diga que vai fazer.\n"
            "REGRA 2: Pode chamar ferramentas várias vezes seguidas. Para ler arquivos do projeto, passe o caminho relativo.\n"
            "REGRA 3: Só responda com texto humano para o usuário quando tiver concluído 100% da tarefa."
        )

        if self.history and self.history[0]["role"] == "system":
            if "[MOTOR BIONIC ATIVADO]" not in self.history[0]["content"]:
                self.history[0]["content"] += bionic_prompt

        log_acoes = []
        usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        for step in range(8):
            print(f"👉 [MOTOR BIONIC] Analisando e Executando (Passo {step+1}/8)...")
            try:
                response, modelo_usado, usage_step = self._chamar_llm_com_fallback(usar_tools=True)
                for k in usage_total:
                    usage_total[k] += usage_step.get(k, 0)

                msg = response.choices[0].message

                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    print(f"   [!] Axel ({modelo_usado}) usou ferramenta nativa: {msg.tool_calls[0].function.name}")
                    resultado_ferramentas = self._processar_tool_calls_interno(msg, log_acoes)
                    if resultado_ferramentas.get("status") == "permissao_pendente":
                        resultado_ferramentas["usage"] = usage_total
                        resultado_ferramentas["modelo"] = modelo_usado
                        return resultado_ferramentas
                    continue

                texto = msg.content or ""
                match = re.search(r'```json\s*(\{.*?"name".*?"arguments".*?\})\s*```', texto, re.DOTALL)
                if match:
                    try:
                        alucinacao_json = json.loads(match.group(1))
                        print(f"   [!] Axel ({modelo_usado}) usou ferramenta local: {alucinacao_json.get('name')}")

                        class FakeFunction:
                            def __init__(self, name, arguments):
                                self.name = name
                                self.arguments = json.dumps(arguments) if isinstance(arguments, dict) else arguments

                        class FakeCall:
                            def __init__(self, func):
                                self.function = func
                                self.id = "call_" + str(uuid.uuid4())[:8]

                        fake_calls = [FakeCall(FakeFunction(alucinacao_json.get("name"), alucinacao_json.get("arguments", {})))]

                        class FakeMsg:
                            def __init__(self, calls, content):
                                self.tool_calls = calls
                                self.content = content

                        resultado_ferramentas = self._processar_tool_calls_interno(FakeMsg(fake_calls, texto), log_acoes)
                        if resultado_ferramentas.get("status") == "permissao_pendente":
                            resultado_ferramentas["usage"] = usage_total
                            resultado_ferramentas["modelo"] = modelo_usado
                            return resultado_ferramentas
                        continue
                    except Exception:
                        pass

                self.history.append({"role": "assistant", "content": texto})

                if log_acoes:
                    log_visual = "\n\n---\n**🧠 [ LOG NEURAL: Operações de Fundo Realizadas ]**\n" + "\n".join(log_acoes)
                    texto += log_visual

                print(f"✅ [MOTOR BIONIC] Tarefa concluída via {modelo_usado}!")
                return {"resposta": texto, "modelo": modelo_usado, "usage": usage_total}

            except Exception as e:
                print(f"❌ [MOTOR BIONIC ERRO]: {str(e)}")
                registrar_evento("agent_error", status="error", detalhes={"step": step, "erro": str(e)[:200]})
                return {"erro": f"Erro BionicAgent (Loop {step}): {str(e)}", "usage": usage_total}

        return {"resposta": "⚠️ Limite de 8 ações autônomas atingido para segurança.", "usage": usage_total}

    def _processar_tool_calls_interno(self, message, log_acoes):
        tool_calls = message.tool_calls

        msg_dict = {"role": "assistant", "content": message.content or ""}
        if tool_calls:
            msg_dict["tool_calls"] = [
                {"id": call.id, "type": "function", "function": {"name": call.function.name, "arguments": call.function.arguments}}
                for call in tool_calls
            ]
        self.history.append(msg_dict)

        for call in tool_calls:
            func_name = call.function.name

            try:
                args = json.loads(call.function.arguments)
            except Exception:
                self.history.append({"role": "tool", "tool_call_id": call.id, "name": func_name, "content": "ERRO: JSON inválido. Tente novamente."})
                log_acoes.append(f"⚠️ IA errou a sintaxe da ferramenta `{func_name}`")
                continue

            if func_name == "run_command":
                cmd = args.get("command", "")
                just = args.get("justificativa", "Terminal")

                if self._comando_eh_proibido(cmd):
                    msg_bloqueio = "BLOQUEADO (AppSec): Comando proibido pela política de segurança."
                    registrar_evento("appsec_block", status="blocked", detalhes={"tool": func_name, "command": cmd})
                    self.history.append({"role": "tool", "tool_call_id": call.id, "name": func_name, "content": msg_bloqueio})
                    log_acoes.append(f"🛡️ Bloqueou comando perigoso: `{cmd}`")
                    continue

                self.comandos_pendentes[call.id] = cmd
                log_acoes.append(f"⚠️ Terminal pendente: `{cmd}`")
                return {"status": "permissao_pendente", "command": cmd, "justificativa": just, "tool_call_id": call.id}

            caminho_bruto = args.get("path", ".")
            caminho_alvo, erro_seguranca = self._validar_caminho_seguro(caminho_bruto)

            if erro_seguranca:
                registrar_evento("appsec_block", status="blocked", detalhes={"tool": func_name, "path": caminho_bruto, "motivo": erro_seguranca})
                self.history.append({"role": "tool", "tool_call_id": call.id, "name": func_name, "content": erro_seguranca})
                log_acoes.append(f"🛡️ {erro_seguranca} (`{caminho_bruto}`)")
                continue

            resultado = ""
            try:
                if func_name == "get_project_tree":
                    if os.path.exists(caminho_alvo) and os.path.isdir(caminho_alvo):
                        itens = [i for i in os.listdir(caminho_alvo) if i.lower() not in PASTAS_BLOQUEADAS and i.lower() != ".env"]
                        resultado = f"Conteúdo de {caminho_alvo}:\n" + "\n".join(itens)
                    else:
                        resultado = "Erro: Diretório não encontrado."
                    log_acoes.append(f"📂 Escaneou: `{caminho_alvo}`")

                elif func_name == "read_file":
                    if os.path.exists(caminho_alvo) and os.path.isfile(caminho_alvo):
                        with open(caminho_alvo, "r", encoding="utf-8") as f:
                            resultado = f.read()
                    else:
                        resultado = f"Erro: Arquivo '{caminho_alvo}' não existe."
                    log_acoes.append(f"📄 Leu arquivo: `{caminho_alvo}`")

                elif func_name == "write_file":
                    conteudo = args.get("content", "")

                    if caminho_alvo.lower().endswith(".py"):
                        try:
                            ast.parse(conteudo)
                        except SyntaxError as se:
                            resultado = f"BLOQUEADO (AST): Erro de sintaxe Python na linha {se.lineno}: {se.msg}. Corrija antes de salvar."
                            registrar_evento("appsec_block", status="blocked", detalhes={"tool": func_name, "path": caminho_alvo, "motivo": f"SyntaxError linha {se.lineno}"})
                            log_acoes.append(f"🛡️ Impediu gravação de Python quebrado em `{caminho_alvo}`")
                            self.history.append({"role": "tool", "tool_call_id": call.id, "name": func_name, "content": resultado})
                            continue

                    os.makedirs(os.path.dirname(caminho_alvo), exist_ok=True)
                    with open(caminho_alvo, "w", encoding="utf-8") as f:
                        f.write(conteudo)
                    resultado = "Sucesso! Arquivo salvo e validado."
                    log_acoes.append(f"💾 Alterou código em: `{caminho_alvo}`")
            except Exception as e:
                resultado = f"Erro de acesso: {e}"
                log_acoes.append(f"❌ Falha em `{caminho_alvo}`")

            self.history.append({"role": "tool", "tool_call_id": call.id, "name": func_name, "content": resultado})

        return {"status": "ok"}

    def aprovar_comando(self, tool_call_id: str, command: str, approved: bool):
        comando_real = self.comandos_pendentes.pop(tool_call_id, command)
        if not approved:
            registrar_evento("terminal_approval", status="denied", detalhes={"command": comando_real})
            self.history.append({"role": "tool", "tool_call_id": tool_call_id, "name": "run_command", "content": "BLOQUEADO PELO USUÁRIO."})
            return {"resposta": "❌ Comando bloqueado por segurança."}

        if self._comando_eh_proibido(comando_real):
            registrar_evento("appsec_block", status="blocked", detalhes={"tool": "run_command", "command": comando_real})
            self.history.append({"role": "tool", "tool_call_id": tool_call_id, "name": "run_command", "content": "BLOQUEADO (AppSec)."})
            return {"resposta": "🛡️ Comando bloqueado pela política de segurança."}

        registrar_evento("terminal_approval", status="approved", detalhes={"command": comando_real})
        try:
            saida = subprocess.getoutput(comando_real)
            resultado = saida if saida.strip() else f"Executado: {comando_real}"
        except Exception as e:
            resultado = f"Erro: {e}"

        self.history.append({"role": "tool", "tool_call_id": tool_call_id, "name": "run_command", "content": resultado})

        try:
            resp, modelo_usado, usage_step = self._chamar_llm_com_fallback(usar_tools=False)
            texto = resp.choices[0].message.content
            self.history.append({"role": "assistant", "content": texto})
            return {"resposta": texto, "modelo": modelo_usado, "usage": usage_step}
        except Exception:
            return {"resposta": f"✅ Comando rodou:\n```\n{resultado}\n```"}
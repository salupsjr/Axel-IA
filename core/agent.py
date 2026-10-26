import os
import json
import requests
from openai import OpenAI
from tools.filesystem import SecureWorkspace
from tools.terminal import SecureTerminal
from tools.multimidia import FerramentasMidia
from rich.console import Console

console = Console()

TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "get_project_tree", "description": "Lista os arquivos do projeto.", "parameters": {"type": "object", "properties": {"relative_path": {"type": "string", "default": "."}}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Lê o conteúdo de um arquivo.", "parameters": {"type": "object", "properties": {"relative_path": {"type": "string"}}, "required": ["relative_path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Escreve código em um arquivo.", "parameters": {"type": "object", "properties": {"relative_path": {"type": "string"}, "content": {"type": "string"}}, "required": ["relative_path", "content"]}}},
    {"type": "function", "function": {"name": "run_command", "description": "Executa comandos no terminal.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "justificativa": {"type": "string", "description": "Explique para o usuário de forma clara o que este comando faz e por que precisa rodá-lo"}}, "required": ["command", "justificativa"]}}},
    {"type": "function", "function": {"name": "gerar_imagem", "description": "Gera uma imagem por IA e salva no projeto.", "parameters": {"type": "object", "properties": {"prompt": {"type": "string", "description": "Descrição da imagem"}, "nome_arquivo": {"type": "string"}}, "required": ["prompt", "nome_arquivo"]}}}
]

class BionicAgent:
    def __init__(self, workspace_path: str, api_key: str):
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        self.workspace = SecureWorkspace(workspace_path)
        self.terminal = SecureTerminal(workspace_path)
        self.midia = FerramentasMidia(workspace_path)
        
        self.history = [
            {"role": "system", "content": "Você é o Caramelo.IA, um agente de código superior. Tem acesso direto à pasta do projeto através de ferramentas. Inspecione, escreva código e valide. NUNCA peça ao usuário para rodar comandos; use a ferramenta run_command e sempre forneça uma justificativa clara."}
        ]
        
        self.modelos_ativos = ["anthropic/claude-3.5-sonnet", "deepseek/deepseek-chat", "qwen/qwen-2.5-72b-instruct"]
        self._atualizar_modelos()
        
    def _atualizar_modelos(self):
        try:
            console.print("[dim]Buscando modelos mais recentes no mercado...[/dim]")
            resposta = requests.get("https://openrouter.ai/api/v1/models").json()
            modelos_api = resposta.get("data", [])
            
            def pegar_mais_novo(prefixo):
                filtrados = [m for m in modelos_api if m["id"].startswith(prefixo) and "preview" not in m["id"]]
                return sorted(filtrados, key=lambda x: x.get("created", 0), reverse=True)[0]["id"] if filtrados else None

            claude_novo, deepseek_novo, qwen_novo = pegar_mais_novo("anthropic/claude-3"), pegar_mais_novo("deepseek/deepseek"), pegar_mais_novo("qwen/qwen")
            nova_lista = [m for m in [claude_novo, deepseek_novo, qwen_novo] if m]
            if nova_lista: self.modelos_ativos = nova_lista
        except Exception as e:
            console.print(f"[bold yellow]Aviso:[/bold yellow] Usando LLMs padrão.")

    def _execute_tool(self, name: str, args: dict) -> str:
        if name == "get_project_tree": return self.workspace.get_project_tree(**args)
        if name == "read_file": return self.workspace.read_file(**args)
        if name == "write_file": return self.workspace.write_file(**args)
        if name == "gerar_imagem": return self.midia.gerar_imagem(**args)
        return "Ferramenta desconhecida."

    def enviar_mensagem(self, user_input: str = None) -> dict:
        if user_input:
            self.history.append({"role": "user", "content": user_input})
        
        ferramentas_usadas = []
        
        while True:
            try:
                response = self.client.chat.completions.create(
                    model=self.modelos_ativos[0],
                    messages=self.history,
                    tools=TOOLS_SCHEMA,
                    tool_choice="auto",
                    extra_body={"route": "fallback", "models": self.modelos_ativos}
                )
            except Exception as e:
                return {"erro": str(e)}

            msg = response.choices[0].message
            modelo_real = response.model
            
            msg_dict = {"role": "assistant"}
            if msg.content: msg_dict["content"] = msg.content
            if msg.tool_calls:
                msg_dict["tool_calls"] = [{"id": t.id, "type": t.type, "function": {"name": t.function.name, "arguments": t.function.arguments}} for t in msg.tool_calls]
            
            self.history.append(msg_dict)

            if not msg.tool_calls:
                return {"status": "sucesso", "resposta": msg.content, "modelo": modelo_real, "ferramentas": ferramentas_usadas}

            pendente_command = None
            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                
                if fn_name == "run_command":
                    cmd_string = fn_args.get("command", "")
                    justificativa = fn_args.get("justificativa", "Executando comando no sistema")
                    
                    # AVALIAÇÃO DO FILTRO DE RISCO
                    if self.terminal.is_safe_command(cmd_string):
                        # É um comando inofensivo. Executa em background sem travar a interface!
                        resultado = self.terminal.execute(cmd_string)
                        ferramentas_usadas.append(f"run_command ({cmd_string}) [Auto-Aprovado]")
                        self.history.append({"role": "tool", "tool_call_id": tool_call.id, "name": fn_name, "content": str(resultado)})
                    else:
                        # É destrutivo ou desconhecido. Manda para aprovação humana (laranja).
                        pendente_command = {
                            "tool_call_id": tool_call.id, 
                            "command": cmd_string,
                            "justificativa": justificativa
                        }
                else:
                    resultado = self._execute_tool(fn_name, fn_args)
                    ferramentas_usadas.append(f"{fn_name}")
                    self.history.append({"role": "tool", "tool_call_id": tool_call.id, "name": fn_name, "content": str(resultado)})
            
            if pendente_command:
                return {
                    "status": "permissao_pendente",
                    "tool_call_id": pendente_command["tool_call_id"],
                    "command": pendente_command["command"],
                    "justificativa": pendente_command["justificativa"],
                    "modelo": modelo_real,
                    "ferramentas": ferramentas_usadas
                }

    def aprovar_comando(self, tool_call_id: str, command: str, aprovado: bool) -> dict:
        if aprovado:
            resultado = self.terminal.execute(command)
        else:
            resultado = "Acesso negado: O utilizador bloqueou a execução deste comando na interface por motivos de segurança."

        self.history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": "run_command",
            "content": str(resultado)
        })
        
        return self.enviar_mensagem(None)
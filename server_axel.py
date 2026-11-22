import os
import re
import time
import socket
import shutil
import subprocess
import psutil
import edge_tts
import pyttsx3
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from openai import OpenAI
from core.agent import BionicAgent
from core.logger import registrar_evento, ler_ultimos_logs
from core.database import (
    init_db,
    sincronizar_obsidian_para_db,
    salvar_mensagem,
    buscar_historico,
    salvar_memoria_db,
    buscar_memorias_relevantes,
    contar_memorias,
)
from personas import SQUAD, ROUTER_PROMPT

try:
    from faster_whisper import WhisperModel
    print("[AXEL] Carregando motor Whisper Local (CPU)...")
    whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    print("[AXEL] Whisper carregado com sucesso na CPU!")
except Exception as e:
    print(f"[AXEL ERRO] Whisper não carregou: {e}")
    whisper_model = None

load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")
ONLINE_MODEL = os.getenv("ONLINE_MODEL", "google/gemini-2.5-flash")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

WORKSPACE_DIR = "./workspace"
AUDIO_DIR = os.path.join(WORKSPACE_DIR, "audio")
MEMORIA_DIR = "./memoria_obsidian"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(MEMORIA_DIR, exist_ok=True)

# Inicializa o banco SQLite e sincroniza notas existentes do Obsidian
init_db()
sincronizar_obsidian_para_db(MEMORIA_DIR)

app = FastAPI(title="AXEL 3D Command Center")

# AppSec: Expõe APENAS a pasta de áudios, nunca os documentos da workspace
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

app.mount("/static", StaticFiles(directory="frontend"), name="static")

agent = BionicAgent(workspace_path=WORKSPACE_DIR, api_key=API_KEY)


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    especialista: str = Field(default="AUTO", max_length=40)
    conclave: bool = False
    modo_foco: bool = False
    voz: bool = True
    historico: list = Field(default_factory=list, max_length=20)
    session_id: str = Field(default="default", max_length=64)


class ApprovalRequest(BaseModel):
    tool_call_id: str = Field(..., min_length=1, max_length=100)
    command: str = Field(default="", max_length=1000)
    approved: bool


class MemoryRequest(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=100)
    conteudo: str = Field(..., min_length=1, max_length=10000)


def verifica_internet():
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=1.5)
        return True
    except OSError:
        return False


def sanitizar_nome_arquivo(nome: str) -> str:
    nome_base = os.path.basename(nome or "arquivo")
    nome_seguro = re.sub(r"[^a-zA-Z0-9._-]", "_", nome_base)
    if not nome_seguro or nome_seguro.startswith("."):
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido ou proibido.")
    return nome_seguro


@app.get("/", response_class=HTMLResponse)
async def carregar_interface():
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/history")
async def obter_historico(session_id: str = "default", limite: int = 20):
    return {"session_id": session_id, "messages": buscar_historico(session_id, limite=limite)}


@app.get("/api/logs")
async def obter_logs(limite: int = 30):
    return {"total": limite, "events": ler_ultimos_logs(limite=limite)}


@app.get("/api/telemetry")
async def telemetria_dell_g7():
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    qtd_memorias = contar_memorias()

    nvidia_usage = 0
    nvidia_vram = 0.0
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        if res.stdout:
            vals = res.stdout.strip().split(",")
            nvidia_usage = int(vals[0].strip())
            nvidia_vram = round(float(vals[1].strip()) / 1024, 1)
    except Exception:
        pass

    return {
        "cpu": cpu,
        "ram_percent": ram.percent,
        "ram_gb": round(ram.used / (1024**3), 1),
        "ram_total": round(ram.total / (1024**3), 1),
        "memorias": qtd_memorias,
        "online": verifica_internet(),
        "nvidia_usage": nvidia_usage,
        "nvidia_vram": nvidia_vram,
        "intel_usage": 0
    }


@app.get("/api/wake_greeting")
async def saudacao_wake_word():
    caminho_mp3 = os.path.join(AUDIO_DIR, "axel_wake.mp3")
    if not os.path.exists(caminho_mp3):
        try:
            com = edge_tts.Communicate(
                "Às suas ordens, Júnior. O que você deseja?",
                voice="pt-BR-AntonioNeural", rate="+12%", pitch="-4Hz"
            )
            await com.save(caminho_mp3)
        except Exception:
            pass
    return {"audio_url": f"/audio/axel_wake.mp3?t={datetime.now().timestamp()}"}


@app.post("/api/memory")
async def salvar_memoria_obsidian(req: MemoryRequest):
    nome_limpo = "".join(c if c.isalnum() else "_" for c in req.titulo[:25]).lower()
    nome_arquivo = f"{datetime.now().strftime('%Y%m%d_%H%M')}_{nome_limpo}.md"
    caminho = os.path.join(MEMORIA_DIR, nome_arquivo)
    conteudo_md = f"# {req.titulo}\nData: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n{req.conteudo}\n"

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo_md)

    salvar_memoria_db(titulo=req.titulo, conteudo=conteudo_md.strip(), arquivo=nome_arquivo)
    registrar_evento("memory_saved", detalhes={"arquivo": nome_arquivo})
    return {"status": "ok", "arquivo": nome_arquivo}


@app.post("/api/upload")
async def upload_arquivo_workspace(file: UploadFile = File(...)):
    nome_seguro = sanitizar_nome_arquivo(file.filename)
    conteudo = await file.read()
    if len(conteudo) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo excede o limite de 10 MB.")

    caminho_destino = os.path.join(WORKSPACE_DIR, nome_seguro)
    with open(caminho_destino, "wb") as buffer:
        buffer.write(conteudo)
    registrar_evento("file_upload", detalhes={"filename": nome_seguro, "bytes": len(conteudo)})
    return {"status": "ok", "filename": nome_seguro}


@app.post("/api/transcribe")
async def transcrever_audio(audio: UploadFile = File(...)):
    if not whisper_model:
        return {"text": "", "erro": "Whisper Local não carregado."}
    caminho_temp = os.path.join(WORKSPACE_DIR, "mic_temp.webm")
    with open(caminho_temp, "wb") as f:
        shutil.copyfileobj(audio.file, f)
    try:
        segments, _ = whisper_model.transcribe(caminho_temp, language="pt")
        texto = " ".join([segment.text for segment in segments])
        return {"text": texto.strip()}
    except Exception as e:
        return {"text": "", "erro": str(e)}


@app.post("/api/chat")
async def processar_comando(req: ChatRequest):
    inicio = time.perf_counter()
    is_online = verifica_internet()

    if not is_online:
        agent.client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
        modelo_rota = OLLAMA_MODEL
    else:
        agent.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)
        agent._atualizar_modelos()
        modelo_rota = ONLINE_MODEL

    especialista_ativo = req.especialista
    if especialista_ativo == "AUTO":
        try:
            print("[ROUTER] Pedindo para o Axel escolher o especialista...")
            resposta_router = agent.client.chat.completions.create(
                model=modelo_rota,
                messages=[{"role": "system", "content": ROUTER_PROMPT.format(prompt=req.prompt)}],
                temperature=0.0,
                max_tokens=10
            )
            decisao = resposta_router.choices[0].message.content.strip().upper()
            decisao = re.sub(r"[^A-Z_]", "", decisao)

            if decisao in SQUAD:
                especialista_ativo = decisao
                print(f"[ROUTER] Axel decidiu rotear para: {especialista_ativo}")
            else:
                especialista_ativo = "AXEL_CORE"
        except Exception as e:
            print(f"[ROUTER ERRO] Falha ao rotear, caindo para o AXEL_CORE. Erro: {e}")
            especialista_ativo = "AXEL_CORE"

    base_prompt = SQUAD.get(especialista_ativo, SQUAD["AXEL_CORE"])
    memoria = buscar_memorias_relevantes(req.prompt, limite=3)

    instrucoes_extras = ""
    if req.modo_foco:
        instrucoes_extras += "\n\n🎯 MODO FOCO ATIVADO: Fatie a solução! Dê APENAS o Passo 1. Recuse-se a dar o Passo 2 até confirmação."

    if req.conclave:
        sys_prompt = f"MODO MEGA-BRAIN CONCLAVE ATIVO.\n1. [{especialista_ativo}]: Solução.\n2. [CRÍTICO]: Riscos.\n3. [VEREDITO]: Ação imediata.\n{instrucoes_extras}\nMemória Relevante:\n{memoria}"
    else:
        sys_prompt = f"Você é o Axel, um assistente IA. Seu criador é o Jr (Salustiano Souza Pires Junior). Nunca se refira a si mesmo como Jr.\n{base_prompt}{instrucoes_extras}\nMemória Relevante do Jr:\n{memoria}"

    agent.history = [{"role": "system", "content": sys_prompt}]

    # Carrega o histórico persistido no SQLite (sobrevive ao F5)
    historico_db = buscar_historico(req.session_id, limite=10)
    for msg in historico_db:
        agent.history.append({
            "role": msg["role"],
            "content": f"O usuário (Jr) disse: {msg['content']}" if msg["role"] == "user" else msg["content"]
        })

    # Persiste a mensagem do usuário no banco
    salvar_mensagem(req.session_id, "user", req.prompt, especialista=especialista_ativo)

    resultado = agent.enviar_mensagem(req.prompt)
    resultado["especialista_real"] = especialista_ativo

    latency_ms = (time.perf_counter() - inicio) * 1000
    registrar_evento(
        "chat_turn",
        session_id=req.session_id,
        especialista=especialista_ativo,
        modelo=resultado.get("modelo"),
        latency_ms=latency_ms,
        usage=resultado.get("usage"),
        status="error" if "erro" in resultado else "ok",
        detalhes={"conclave": req.conclave, "modo_foco": req.modo_foco, "offline": not is_online}
    )

    if resultado.get("resposta"):
        salvar_mensagem(
            req.session_id,
            "assistant",
            resultado["resposta"],
            especialista=especialista_ativo,
            modelo=resultado.get("modelo")
        )

    audio_url = None
    texto_chat = str(resultado.get("resposta") or "[Sem resposta. O modelo local pode estar desligado ou sobrecarregado.]")

    texto_falado = re.sub(r"```.*?```", " [bloco de código na tela] ", texto_chat, flags=re.DOTALL)
    texto_falado = texto_falado.replace("*", "").replace("#", "").replace("`", "")
    texto_falado = texto_falado.replace("<", " ").replace(">", " ")
    texto_falado = texto_falado[:4000]

    if req.voz and resultado.get("resposta"):
        caminho_mp3 = os.path.join(AUDIO_DIR, "axel_speech.mp3")
        try:
            if is_online:
                com = edge_tts.Communicate(texto_falado, voice="pt-BR-AntonioNeural", rate="+12%", pitch="-4Hz")
                await com.save(caminho_mp3)
            else:
                engine = pyttsx3.init()
                voices = engine.getProperty("voices")
                for voice in voices:
                    if "brazil" in voice.name.lower() or "portuguese" in voice.name.lower():
                        engine.setProperty("voice", voice.id)
                        break
                engine.save_to_file(texto_falado, caminho_mp3)
                engine.runAndWait()

            audio_url = f"/audio/axel_speech.mp3?t={datetime.now().timestamp()}"
        except Exception as e:
            print(f"\n[AXEL ERRO DE VOZ]: Falha ao gerar o áudio. Erro: {e}\n")

    resultado["audio_url"] = audio_url
    resultado["is_offline"] = not is_online
    return resultado


@app.post("/api/approve")
async def aprovar_comando(req: ApprovalRequest):
    return agent.aprovar_comando(req.tool_call_id, req.command, req.approved)
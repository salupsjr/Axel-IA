import os
import json
from datetime import datetime

LOGS_DIR = os.path.join(os.getcwd(), "logs")
LOG_FILE = os.path.join(LOGS_DIR, "axel_events.jsonl")
os.makedirs(LOGS_DIR, exist_ok=True)


def registrar_evento(
    event_type: str,
    session_id: str = "default",
    especialista: str = None,
    modelo: str = None,
    latency_ms: float = None,
    usage: dict = None,
    detalhes: dict = None,
    status: str = "ok"
):
    """Grava um evento estruturado em formato JSON Lines (1 JSON por linha)."""
    registro = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "status": status,
        "session_id": session_id,
        "especialista": especialista,
        "modelo": modelo,
        "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
        "tokens": usage or {},
        "detalhes": detalhes or {}
    }
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[LOGGER ERRO] Não foi possível gravar log: {e}")


def ler_ultimos_logs(limite: int = 30) -> list:
    """Retorna os últimos eventos gravados (mais recentes primeiro)."""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            linhas = f.readlines()
        eventos = [json.loads(l) for l in linhas[-limite:] if l.strip()]
        return list(reversed(eventos))
    except Exception:
        return []
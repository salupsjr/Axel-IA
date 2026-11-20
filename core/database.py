import os
import re
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    from supabase import create_client
except ImportError:
    create_client = None

DB_PATH = os.path.join(os.getcwd(), "axel_memory.db")
_supabase_client = None


def _get_supabase():
    """Retorna o cliente Supabase se configurado e fora de ambiente pytest."""
    global _supabase_client
    if os.getenv("PYTEST_CURRENT_TEST") or create_client is None:
        return None
    if _supabase_client is not None:
        return _supabase_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if url and key:
        try:
            _supabase_client = create_client(url, key)
        except Exception as e:
            print(f"[DB WARN] Falha ao iniciar Supabase, usando SQLite local: {e}")
            return None
    return _supabase_client


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Inicializa o banco SQLite local (cache e fallback offline)."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL DEFAULT 'default',
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                especialista TEXT,
                modelo TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                arquivo TEXT UNIQUE,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def salvar_mensagem(session_id: str, role: str, content: str, especialista: str = None, modelo: str = None):
    agora = datetime.now().isoformat()

    # 1. Sempre salva no SQLite local (cache/offline)
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, especialista, modelo, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, role, content, especialista, modelo, agora)
        )
        conn.commit()

    # 2. Sincroniza com o Supabase se estiver online
    sb = _get_supabase()
    if sb:
        try:
            sb.table("messages").insert({
                "session_id": session_id,
                "role": role,
                "content": content,
                "especialista": especialista,
                "modelo": modelo,
            }).execute()
        except Exception as e:
            print(f"[SUPABASE WARN] Falha ao salvar mensagem na nuvem: {e}")


def buscar_historico(session_id: str = "default", limite: int = 10) -> list:
    sb = _get_supabase()
    if sb:
        try:
            res = (
                sb.table("messages")
                .select("role, content, especialista, modelo, created_at")
                .eq("session_id", session_id)
                .order("id", desc=True)
                .limit(limite)
                .execute()
            )
            if res.data is not None:
                return list(reversed(res.data))
        except Exception as e:
            print(f"[SUPABASE WARN] Falha ao ler histórico da nuvem, usando SQLite: {e}")

    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, especialista, modelo, created_at FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limite)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def salvar_memoria_db(titulo: str, conteudo: str, arquivo: str):
    agora = datetime.now().isoformat()

    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO memories (titulo, conteudo, arquivo, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(arquivo) DO UPDATE SET titulo=excluded.titulo, conteudo=excluded.conteudo
            """,
            (titulo, conteudo, arquivo, agora)
        )
        conn.commit()

    sb = _get_supabase()
    if sb:
        try:
            sb.table("memories").upsert(
                {"titulo": titulo, "conteudo": conteudo, "arquivo": arquivo},
                on_conflict="arquivo"
            ).execute()
        except Exception as e:
            print(f"[SUPABASE WARN] Falha ao sincronizar memória na nuvem: {e}")


def sincronizar_obsidian_para_db(memoria_dir: str):
    if not os.path.exists(memoria_dir):
        return
    for nome in os.listdir(memoria_dir):
        if nome.endswith(".md"):
            caminho = os.path.join(memoria_dir, nome)
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    conteudo = f.read().strip()
                titulo = nome.replace(".md", "")
                salvar_memoria_db(titulo=titulo, conteudo=conteudo, arquivo=nome)
            except Exception:
                continue


def buscar_memorias_relevantes(query: str, limite: int = 3) -> str:
    rows = []
    sb = _get_supabase()
    if sb:
        try:
            res = sb.table("memories").select("titulo, conteudo, arquivo").execute()
            rows = res.data or []
        except Exception as e:
            print(f"[SUPABASE WARN] Falha ao buscar memórias na nuvem, usando SQLite: {e}")

    if not rows:
        with _get_conn() as conn:
            rows = [dict(r) for r in conn.execute("SELECT titulo, conteudo, arquivo FROM memories").fetchall()]

    if not rows:
        return "Nenhuma memória salva ainda."

    palavras = {p for p in re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}", (query or "").lower())}
    pontuadas = []
    for r in rows:
        texto_lower = f"{r['titulo']} {r['conteudo']}".lower()
        score = sum(1 for p in palavras if p in texto_lower)
        pontuadas.append((score, r))

    pontuadas.sort(key=lambda x: x[0], reverse=True)
    selecionadas = [r for score, r in pontuadas[:limite] if score > 0]
    if not selecionadas:
        selecionadas = [r for _, r in pontuadas[:1]]

    return "\n\n---\n\n".join(f"[{r['arquivo']}]\n{r['conteudo']}" for r in selecionadas)


def contar_memorias() -> int:
    sb = _get_supabase()
    if sb:
        try:
            res = sb.table("memories").select("id", count="exact").execute()
            if res.count is not None:
                return res.count
        except Exception:
            pass

    with _get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as total FROM memories").fetchone()
    return row["total"] if row else 0
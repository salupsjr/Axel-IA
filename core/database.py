import os
import re
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.getcwd(), "axel_memory.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Cria as tabelas de histórico e memória se não existirem."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
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
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (session_id, role, content, especialista, modelo, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, role, content, especialista, modelo, datetime.now().isoformat())
        )
        conn.commit()


def buscar_historico(session_id: str, limite: int = 10) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limite)
        ).fetchall()
    # Retorna em ordem cronológica (mais antiga -> mais recente)
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def salvar_memoria_db(titulo: str, conteudo: str, arquivo: str = None):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO memories (titulo, conteudo, arquivo, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (titulo, conteudo, arquivo, datetime.now().isoformat())
        )
        conn.commit()


def sincronizar_obsidian_para_db(memoria_dir: str):
    """Importa arquivos .md existentes em memoria_obsidian/ para o banco SQLite."""
    if not os.path.exists(memoria_dir):
        return
    for arq in sorted(os.listdir(memoria_dir)):
        if arq.endswith(".md"):
            caminho = os.path.join(memoria_dir, arq)
            with open(caminho, "r", encoding="utf-8") as f:
                conteudo = f.read().strip()
            titulo = arq.replace(".md", "")
            salvar_memoria_db(titulo=titulo, conteudo=conteudo, arquivo=arq)


def buscar_memorias_relevantes(query: str, limite: int = 3) -> str:
    """Retorna apenas as memórias mais relevantes para o prompt atual (economiza tokens)."""
    with get_connection() as conn:
        rows = conn.execute("SELECT titulo, conteudo, arquivo FROM memories ORDER BY id DESC").fetchall()

    if not rows:
        return "Sem notas gravadas na Memória Eterna."

    # Extrai palavras-chave relevantes (>= 4 letras) do prompt
    termos = {w for w in re.findall(r"\w+", query.lower()) if len(w) >= 4}

    pontuadas = []
    for r in rows:
        texto_completo = f"{r['titulo']} {r['conteudo']}".lower()
        score = sum(1 for t in termos if t in texto_completo)
        pontuadas.append((score, r))

    # Ordena por relevância (maior score primeiro)
    pontuadas.sort(key=lambda x: x[0], reverse=True)
    selecionadas = [r for score, r in pontuadas[:limite] if score > 0]

    # Se nenhuma palavra bateu, injeta apenas a nota mais recente como contexto base
    if not selecionadas:
        selecionadas = [rows[0]]

    return "\n\n".join(f"[{r['arquivo'] or r['titulo']}]:\n{r['conteudo']}" for r in selecionadas)


def contar_memorias() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as total FROM memories").fetchone()
        return row["total"] if row else 0
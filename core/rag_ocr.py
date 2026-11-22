import os
import base64
from dotenv import load_dotenv
from core.database import salvar_memoria_db

load_dotenv()

try:
    import pymupdf
except ImportError:
    pymupdf = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

GEMINI_VISION_MODELS = [
    os.getenv("GEMINI_VISION_MODEL", "gemini-3.8-flash"),
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-4-neon",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
]
OPENROUTER_VISION_MODEL = os.getenv("VISION_MODEL", "google/gemini-2.5-flash")
MAX_OCR_PAGES = 15


def _extrair_texto_gemini_direto(caminho_pdf: str) -> str:
    """Usa a GEMINI_API_KEY direta com fallback automático entre modelos em caso de 503/404."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or genai is None or pymupdf is None:
        return ""

    client = genai.Client(api_key=api_key)
    doc = pymupdf.open(caminho_pdf)
    total_paginas = min(len(doc), MAX_OCR_PAGES)
    textos = []

    lote_tamanho = 5
    for inicio in range(0, total_paginas, lote_tamanho):
        fim = min(inicio + lote_tamanho, total_paginas)
        contents = [
            (
                f"Transcreva fielmente todo o texto destas páginas ({inicio + 1} a {fim}) "
                "de um documento em português. Preserve nomes, CNPJs, CPFs, cláusulas, "
                "quotas, valores e poderes de assinatura. Retorne apenas o texto transcrito."
            )
        ]

        for p in range(inicio, fim):
            pix = doc[p].get_pixmap(dpi=140)
            contents.append(
                types.Part.from_bytes(data=pix.tobytes("jpeg"), mime_type="image/jpeg")
            )

        trecho = ""
        for modelo in dict.fromkeys(GEMINI_VISION_MODELS):
            try:
                resp = client.models.generate_content(
                    model=modelo,
                    contents=contents,
                )
                trecho = (resp.text or "").strip()
                if trecho:
                    print(f"[RAG OCR] Lote {inicio + 1}-{fim} transcrito com sucesso via {modelo}.")
                    break
            except Exception as e:
                print(f"[RAG OCR WARN] {modelo} falhou no lote {inicio + 1}-{fim}: {e}")

        if trecho:
            textos.append(f"--- PÁGINAS {inicio + 1} A {fim} ---\n{trecho}")

    doc.close()
    return "\n\n".join(textos).strip()


def _extrair_texto_openrouter(caminho_pdf: str) -> str:
    """Fallback via OpenRouter (com max_tokens controlado para evitar erro 402)."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or OpenAI is None or pymupdf is None:
        return ""

    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    doc = pymupdf.open(caminho_pdf)
    total_paginas = min(len(doc), MAX_OCR_PAGES)
    textos = []

    lote_tamanho = 5
    for inicio in range(0, total_paginas, lote_tamanho):
        fim = min(inicio + lote_tamanho, total_paginas)
        content = [
            {
                "type": "text",
                "text": (
                    f"Transcreva fielmente todo o texto destas páginas ({inicio + 1} a {fim}) "
                    "de um documento em português. Preserve nomes, CNPJs, CPFs, cláusulas, "
                    "quotas, valores e poderes de assinatura. Retorne apenas o texto transcrito."
                )
            }
        ]

        for p in range(inicio, fim):
            pix = doc[p].get_pixmap(dpi=130)
            img_b64 = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
            })

        try:
            resp = client.chat.completions.create(
                model=OPENROUTER_VISION_MODEL,
                messages=[{"role": "user", "content": content}],
                temperature=0.0,
                max_tokens=1000,
            )
            trecho = (resp.choices[0].message.content or "").strip()
            if trecho:
                textos.append(f"--- PÁGINAS {inicio + 1} A {fim} ---\n{trecho}")
        except Exception as e:
            print(f"[RAG OCR OPENROUTER WARN] Falha no lote {inicio + 1}-{fim}: {e}")

    doc.close()
    return "\n\n".join(textos).strip()


def indexar_documento_rag(caminho: str, nome_arquivo: str) -> dict:
    """Extrai texto (nativo ou OCR por visão), divide em blocos e salva no Supabase pgvector."""
    ext = os.path.splitext(nome_arquivo)[1].lower()
    texto = ""
    metodo = "vazio"

    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(caminho)
            texto = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
            if len(texto) >= 100:
                metodo = "texto_nativo"
        except Exception as e:
            print(f"[RAG PDF WARN] Erro no pypdf em {nome_arquivo}: {e}")

        if len(texto) < 100:
            print(f"[RAG OCR] PDF escaneado detectado ({nome_arquivo}). Iniciando OCR com fallback Gemini...")
            texto = _extrair_texto_gemini_direto(caminho)
            if texto:
                metodo = "ocr_gemini_direto"
            else:
                print("[RAG OCR] Tentando fallback via OpenRouter...")
                texto = _extrair_texto_openrouter(caminho)
                if texto:
                    metodo = "ocr_openrouter"

    elif ext in {".txt", ".md", ".csv", ".json"}:
        try:
            with open(caminho, "r", encoding="utf-8", errors="ignore") as f:
                texto = f.read().strip()
            if texto:
                metodo = "texto_nativo"
        except Exception:
            return {"chunks": 0, "metodo": "erro"}
    else:
        return {"chunks": 0, "metodo": "nao_suportado"}

    if not texto:
        return {"chunks": 0, "metodo": "vazio"}

    # Divide em blocos de 1500 caracteres com sobreposição de 200
    tamanho, overlap = 1500, 200
    blocos = []
    pos = 0
    while pos < len(texto):
        bloco = texto[pos:pos + tamanho].strip()
        if bloco:
            blocos.append(bloco)
        pos += tamanho - overlap

    limite_blocos = min(len(blocos), 25)
    for idx, bloco in enumerate(blocos[:limite_blocos], start=1):
        salvar_memoria_db(
            titulo=f"{nome_arquivo} (Parte {idx}/{limite_blocos})",
            conteudo=bloco,
            arquivo=f"doc_{nome_arquivo}_p{idx}"
        )

    return {"chunks": limite_blocos, "metodo": metodo}
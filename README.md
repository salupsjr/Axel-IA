# AXEL // 3D Command Center

[![CI](https://github.com/salupsjr/Axel-IA/actions/workflows/ci.yml/badge.svg)](https://github.com/salupsjr/Axel-IA/actions)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![Three.js](https://img.shields.io/badge/Three.js-3D%20HUD-000000?logo=threedotjs&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-pgvector-3FCF8E?logo=supabase&logoColor=white)

Assistente pessoal e orquestrador multi-agente com interface 3D interativa, roteamento inteligente de especialistas, memória híbrida com busca vetorial (**`pgvector`** + **SQLite** + **Obsidian `.md`**), transcrição de voz local (**Faster-Whisper**) e ingestão automática de documentos — incluindo **OCR por visão** para PDFs escaneados.

---

## Arquitetura em Alto Nível

- **Frontend 3D & Responsivo:** Interface em HTML/CSS/JS com núcleo neural em **Three.js** (suporte a mouse e toque no mobile), telemetria do sistema em tempo real, seleção de especialistas, modo foco, conclave e controle de voz.
- **Backend & Orquestração (`FastAPI`):** Endpoints REST para chat, roteamento automático (`ROUTER_PROMPT`), aprovação explícita de comandos sensíveis (`Human-in-the-Loop`), transcrição de áudio (`/api/transcribe`), upload e indexação de documentos (`/api/upload`).
- **Squad de Especialistas:** `AXEL_CORE`, `ARCHITECT`, `DEVELOPER`, `AUDITOR_PJ`, `ANALYST`, `GROWTH`, `ROUTINE` e `CRITICO`.
- **RAG & OCR de Documentos:** Extração de texto nativo (`pypdf`) com fallback automático para **OCR por visão** (`PyMuPDF` + modelos Gemini com fallback em cadeia) para PDFs escaneados (como contratos sociais, atas e documentos PJ), fatiados em blocos e persistidos no banco.
- **Voz Bidirecional:** Entrada por voz via **Faster-Whisper** (`int8` em CPU) e saída por voz via **Edge TTS** (online) com fallback para **pyttsx3** (offline).

---

## Estrutura do Projeto

```text
Axel-IA/
├── core/
│   ├── agent.py          # Núcleo do agente e execução com controle de permissão
│   ├── database.py       # Persistência híbrida (SQLite + Supabase pgvector + histórico)
│   ├── logger.py         # Registro estruturado de eventos e telemetria de latência
│   └── rag_ocr.py        # Extração de PDF/TXT/MD, OCR por visão e chunking RAG
├── frontend/
│   ├── index.html        # Command Center 3D e painel de controle
│   └── js/app.js         # Cena Three.js, áudio, microfone, upload RAG e histórico
├── memoria_obsidian/     # Notas em Markdown sincronizadas com a base de conhecimento
├── workspace/            # Arquivos anexados e áudios gerados (não expostos diretamente)
├── personas.py           # Prompts dos especialistas e roteador neural
├── server_axel.py        # Aplicação FastAPI principal
└── requirements.txt      # Dependências do projeto


## Como Rodar Localmente
Clone o repositório e ative o ambiente virtual:

Bash
git clone [https://github.com/salupsjr/Axel-IA.git](https://github.com/salupsjr/Axel-IA.git)
cd Axel-IA
python -m venv venv
.\venv\Scripts\Activate.ps1
Instale as dependências:

Bash
pip install -r requirements.txt
pip install pypdf pymupdf
Configure as variáveis de ambiente (.env):

## Snippet de código
OPENROUTER_API_KEY=sua_chave_openrouter
ONLINE_MODEL=google/gemini-2.5-flash
GEMINI_API_KEY=sua_chave_gemini
GEMINI_VISION_MODEL=gemini-3.8-flash
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:3b
SUPABASE_URL=sua_url_supabase
SUPABASE_KEY=sua_chave_supabase
Inicie o servidor:

Bash
uvicorn server_axel:app --host 0.0.0.0 --port 8000 --reload
Acesse http://localhost:8000 no navegador.

## Segurança e Boas Práticas
Human-in-the-Loop: Comandos de sistema exigem aprovação explícita antes da execução.

Isolamento de Arquivos: A pasta workspace/ não é exposta como diretório estático público; apenas /audio é servido via StaticFiles.

Sanitização de Uploads: Validação de tamanho máximo e higienização de nomes de arquivos no endpoint /api/upload.
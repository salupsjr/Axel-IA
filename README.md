# 🧠 AXEL // 3D Command Center

O **AXEL** é um assistente de Inteligência Artificial autônomo, híbrido (Online/Offline) e blindado (AppSec), equipado com interface HUD 3D interativa, roteamento multi-especialistas, fallback automático entre LLMs, persistência em SQLite e observabilidade estruturada.

---

## 🏗️ Arquitetura (6 Camadas)

1. **Interface (`frontend/index.html`):** HUD 3D construído com Three.js e TailwindCSS, desacoplado do backend, com telemetria em tempo real e controle de voz.
2. **Backend & Segurança (`server_axel.py`):** Gateway FastAPI com validação Pydantic, sanitização de uploads (limite de 10 MB) e exposição estática restrita apenas a `/audio/`.
3. **Orquestração (`core/agent.py`):** Motor *Bionic* com loop controlado (máximo 8 passos), aprovação humana (*Human-in-the-Loop*) para terminal, proteção contra *Path Traversal*, bloqueio de `.env` e validação de sintaxe Python (`ast.parse`) antes de gravar código.
4. **Modelos (Multi-LLM Fallback):** Cascata automática **OpenRouter Principal → OpenRouter Gratuito → Ollama Local (`qwen2.5:3b`)** em caso de falta de créditos (`402`), rate limit (`429`) ou queda de internet.
5. **Memória & Dados (`core/database.py`):** Banco **SQLite (`axel_memory.db`)** para histórico persistente por sessão e indexação/busca por relevância das notas de `memoria_obsidian/`.
6. **Observabilidade (`core/logger.py`):** Logs estruturados em JSON Lines (`logs/axel_events.jsonl`) registrando latência, consumo de tokens, fallbacks e bloqueios de segurança, auditáveis via `/api/logs`.

---

## 📂 Estrutura do Projeto

```text
Axel-IA/
├── core/
│   ├── agent.py             # Motor Bionic (AppSec, AST check, Fallback Multi-LLM)
│   ├── database.py          # Persistência SQLite (histórico + busca de memórias)
│   └── logger.py            # Observabilidade estruturada (JSONL)
├── frontend/
│   └── index.html           # Interface HUD 3D (Three.js + TailwindCSS)
├── logs/                    # Logs auditáveis em JSONL (ignorado no Git)
├── memoria_obsidian/        # Notas pessoais em Markdown (ignorado no Git)
├── workspace/               # Uploads e pasta audio/ (ignorado no Git)
├── personas.py              # Squad de 8 especialistas + Router Neural
├── server_axel.py           # Backend FastAPI, Whisper local e TTS híbrido
├── requirements.txt         # Dependências travadas do projeto
├── .env.example             # Template seguro de variáveis de ambiente
├── .gitignore               # Blindagem contra vazamento de segredos e dados
└── README.md                # Documentação do projeto

🚀 Instalação e Execução
1. Crie e ative o ambiente virtual (Windows PowerShell)
PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1
2. Instale as dependências
PowerShell
pip install -r requirements.txt
3. Configure o ambiente
Copie o .env.example para .env e preencha sua chave da OpenRouter:

PowerShell
copy .env.example .env
4. Inicie o servidor
PowerShell
uvicorn server_axel:app --reload
🌐 Rotas Principais
GET / — Interface HUD 3D do Axel.

POST /api/chat — Envia comandos ao orquestrador multi-especialistas.

GET /api/history — Consulta o histórico persistido no SQLite.

GET /api/logs — Auditoria de eventos, latência, tokens e bloqueios AppSec.

GET /api/telemetry — Telemetria de hardware (CPU, RAM, GPU).

---


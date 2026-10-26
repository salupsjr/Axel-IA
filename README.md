# 🐶 Caramelo.IA - Agente Autônomo Multi-IA

Um sistema de Inteligência Artificial autônomo construído em Python, capaz de escrever código, manipular arquivos e interagir com o sistema operacional de forma segura através de uma interface web.

## 🚀 Tecnologias Utilizadas
* **Linguagem:** Python
* **Interface:** Streamlit
* **Integração LLM:** OpenRouter API (Claude 3.5 Sonnet, DeepSeek, Qwen)
* **Arquitetura:** Multi-Agent Routing com Fallback automático.

## ⚙️ Funcionalidades Atuais
- [x] **Roteamento Inteligente:** Atualização automática para as versões mais recentes das LLMs no mercado.
- [x] **Segurança Human-in-the-Loop:** Interceptação visual de comandos de terminal. A IA precisa justificar a ação e pedir permissão antes de executar comandos no sistema do usuário.
- [x] **Manipulação de Arquivos:** Leitura nativa de PDFs, planilhas (Excel/CSV) e escrita autônoma de código no workspace.
- [x] **Stateful Memory:** Histórico de conversas persistente em JSON com capacidade de "Save State" (edição de mensagens com rollback de memória do agente).

## 🔒 Como rodar localmente
1. Clone este repositório.
2. Crie um ambiente virtual: `python -m venv venv` e ative-o.
3. Instale as dependências: `pip install streamlit openai requests PyPDF2 pandas openpyxl`
4. Crie um arquivo `.env` na raiz e adicione sua chave: `OPENROUTER_API_KEY=sua_chave_aqui`
5. Execute: `streamlit run app.py`
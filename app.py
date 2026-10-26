import os
import json
import streamlit as st
from dotenv import load_dotenv
from core.agent import BionicAgent
from datetime import datetime

st.set_page_config(page_title="Caramelo.IA", page_icon="🐶", layout="wide")

load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")
WORKSPACE_DIR = "./workspace"
HISTORICO_FILE = "chats.json"

def carregar_chats():
    if os.path.exists(HISTORICO_FILE):
        with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_chats(chats):
    with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
        json.dump(chats, f, ensure_ascii=False, indent=4)

if "chats" not in st.session_state: st.session_state.chats = carregar_chats()
if "agent" not in st.session_state: st.session_state.agent = BionicAgent(workspace_path=WORKSPACE_DIR, api_key=API_KEY)
if "editando_idx" not in st.session_state: st.session_state.editando_idx = None
if "reprocessar_prompt" not in st.session_state: st.session_state.reprocessar_prompt = None
if "comando_pendente" not in st.session_state: st.session_state.comando_pendente = None

if not st.session_state.chats:
    novo_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.chats[novo_id] = {"titulo": "Nova Conversa", "mensagens": [], "history_agente": [{"role": "system", "content": "Você é o Caramelo.IA, um agente de código superior..."}]}
    st.session_state.chat_atual = novo_id
    salvar_chats(st.session_state.chats)

if "chat_atual" not in st.session_state or st.session_state.chat_atual is None:
    st.session_state.chat_atual = list(st.session_state.chats.keys())[-1] if st.session_state.chats else None

# ==========================================
# BARRA LATERAL (Apenas Histórico e Novo Chat)
# ==========================================
with st.sidebar:
    col1, col2 = st.columns([0.8, 0.2])
    col1.title("🐶 Caramelo.IA")
    
    if col2.button("📝", help="Nova Conversa", type="primary"):
        novo_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.chats[novo_id] = {"titulo": "Nova Conversa", "mensagens": [], "history_agente": [{"role": "system", "content": "Você é o Caramelo.IA..."}]}
        st.session_state.chat_atual = novo_id
        st.session_state.editando_idx = None
        st.session_state.comando_pendente = None
        salvar_chats(st.session_state.chats)
        st.rerun()

    st.markdown("---")
    st.markdown("### 📝 Histórico")
    chats_para_remover = []
    for chat_id, chat_data in reversed(list(st.session_state.chats.items())):
        c_nome, c_del = st.columns([0.85, 0.15])
        if c_nome.button(chat_data["titulo"], key=f"chat_{chat_id}", use_container_width=True):
            st.session_state.chat_atual = chat_id
            st.session_state.editando_idx = None
            st.session_state.comando_pendente = None
            st.rerun()
        if c_del.button("🗑️", key=f"del_{chat_id}", help="Excluir conversa"):
            chats_para_remover.append(chat_id)
            
    if chats_para_remover:
        for cid in chats_para_remover:
            del st.session_state.chats[cid]
        if not st.session_state.chats:
            st.session_state.chat_atual = None
        elif st.session_state.chat_atual in chats_para_remover:
            st.session_state.chat_atual = list(st.session_state.chats.keys())[-1]
            
        st.session_state.editando_idx = None
        st.session_state.comando_pendente = None
        salvar_chats(st.session_state.chats)
        st.rerun()

# ==========================================
# ÁREA PRINCIPAL DO CHAT
# ==========================================
chat_ativo = st.session_state.chats.get(st.session_state.chat_atual)

if chat_ativo:
    st.session_state.agent.history = chat_ativo["history_agente"]

    def tratar_resultado_ia(resultado, ferramentas_anteriores=None):
        ferramentas_anteriores = ferramentas_anteriores or []
        chat_ativo["history_agente"] = st.session_state.agent.history
        salvar_chats(st.session_state.chats)

        if resultado.get("status") == "permissao_pendente":
            st.session_state.comando_pendente = resultado
            st.rerun()
        elif "erro" in resultado:
            st.error(f"Erro: {resultado['erro']}")
        else:
            texto_ia = resultado["resposta"]
            modelo_usado = resultado["modelo"]
            ferramentas = ferramentas_anteriores + resultado.get("ferramentas", [])
            
            chat_ativo["mensagens"].append({"autor": "assistant", "texto": texto_ia, "modelo": modelo_usado, "ferramentas": ferramentas})
            salvar_chats(st.session_state.chats)
            st.rerun()

    for i, msg in enumerate(chat_ativo["mensagens"]):
        nome = "Jr" if msg["autor"] == "user" else f"Caramelo ({msg.get('modelo', 'IA')})"
        with st.chat_message(msg["autor"]):
            if msg["autor"] == "user":
                col_txt, col_btn = st.columns([0.95, 0.05])
                col_txt.markdown(f"**{nome}:** {msg['texto']}")
                if col_btn.button("✏️", key=f"btn_{i}"):
                    st.session_state.editando_idx = i
                    st.rerun()

                if st.session_state.editando_idx == i:
                    novo_texto = st.text_area("Edite sua mensagem:", value=msg['texto'], key=f"area_{i}")
                    c1, c2 = st.columns(2)
                    if c1.button("Salvar e Reenviar", key=f"save_{i}"):
                        idx_agente = msg["history_idx"]
                        chat_ativo["mensagens"] = chat_ativo["mensagens"][:i]
                        chat_ativo["history_agente"] = chat_ativo["history_agente"][:idx_agente]
                        st.session_state.editando_idx = None
                        st.session_state.reprocessar_prompt = novo_texto
                        salvar_chats(st.session_state.chats)
                        st.rerun()
                    if c2.button("Cancelar", key=f"cancel_{i}"):
                        st.session_state.editando_idx = None
                        st.rerun()
            else:
                st.markdown(f"**{nome}:** {msg['texto']}")
                if msg.get("ferramentas"):
                    with st.expander("🛠️ Ferramentas executadas"):
                        st.code("\n".join(msg["ferramentas"]))

    # ==========================================
    # ÁREA DE INPUT INFERIOR E BOTÃO DE ANEXO
    # ==========================================
    if st.session_state.comando_pendente:
        pendente = st.session_state.comando_pendente
        st.warning(f"⚠️ **Caramelo.IA pede permissão para agir no seu sistema:**\n\n**Por quê?** {pendente.get('justificativa', 'Sem justificativa')}\n\n**O que será executado:**\n`{pendente['command']}`")
        c1, c2, _ = st.columns([0.15, 0.15, 0.7])
        
        if c1.button("✅ Permitir", type="primary"):
            with st.spinner("Executando no sistema..."):
                res = st.session_state.agent.aprovar_comando(pendente["tool_call_id"], pendente["command"], True)
                st.session_state.comando_pendente = None
                tratar_resultado_ia(res, pendente["ferramentas"])
                
        if c2.button("❌ Bloquear"):
            with st.spinner("Avisando a IA do bloqueio..."):
                res = st.session_state.agent.aprovar_comando(pendente["tool_call_id"], pendente["command"], False)
                st.session_state.comando_pendente = None
                tratar_resultado_ia(res, pendente["ferramentas"])
    else:
        # BOTÃO RETRÁTIL INFERIOR (Design Nativo e Seguro)
        col_anexo, col_vazia = st.columns([0.05, 0.95])
        
        with col_anexo:
            with st.popover("+", help="Anexar Documento ou Imagem"):
                arquivo_up = st.file_uploader("Upload", label_visibility="collapsed")
                if arquivo_up:
                    caminho_salvar = os.path.join(WORKSPACE_DIR, arquivo_up.name)
                    with open(caminho_salvar, "wb") as f:
                        f.write(arquivo_up.getbuffer())
                    st.success(f"✅ {arquivo_up.name} salvo!")

        prompt_editado = st.session_state.reprocessar_prompt
        prompt_padrao = st.chat_input("Digite seu comando, Jr...")
        prompt = prompt_editado or prompt_padrao

        if prompt:
            st.session_state.reprocessar_prompt = None
            if chat_ativo["titulo"] == "Nova Conversa":
                chat_ativo["titulo"] = prompt[:25] + "..."

            idx_memoria_atual = len(st.session_state.agent.history)
            chat_ativo["mensagens"].append({"autor": "user", "texto": prompt, "history_idx": idx_memoria_atual})
            
            with st.chat_message("user"):
                st.markdown(f"**Jr:** {prompt}")

            with st.chat_message("assistant"):
                with st.spinner("Processando..."):
                    resultado = st.session_state.agent.enviar_mensagem(prompt)
                    tratar_resultado_ia(resultado)
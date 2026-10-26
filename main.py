import os
from dotenv import load_dotenv
from core.agent import BionicAgent

# Carrega a chave do ficheiro .env
load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    print("Erro: A GEMINI_API_KEY não foi encontrada no ficheiro .env!")
    exit(1)

if __name__ == "__main__":
    agente = BionicAgent(
        workspace_path="./workspace", 
        api_key=API_KEY
    )
    
    agente.chat_loop()
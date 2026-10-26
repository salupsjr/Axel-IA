import os
from dotenv import load_dotenv
from google import genai

# Carrega a sua chave AQ... do arquivo .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

print("Consultando servidores do Google...\n")
print("Modelos disponíveis para a sua chave:")
print("-" * 40)

# Busca e imprime apenas o nome oficial do modelo
for model in client.models.list():
    print(model.name)
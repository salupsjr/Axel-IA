import os
import requests
from urllib.parse import quote
from rich.console import Console

console = Console()

class FerramentasMidia:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir

    def gerar_imagem(self, prompt: str, nome_arquivo: str) -> str:
        console.print(f"\n[bold magenta]🎨 A IA está gerando uma imagem:[/bold magenta] {prompt}")
        try:
            # Pollinations.ai é gratuito, sem chave, e aceita prompts complexos
            url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?nologo=true"
            resposta = requests.get(url)
            
            if resposta.status_code == 200:
                caminho_completo = os.path.join(self.workspace_dir, nome_arquivo)
                with open(caminho_completo, 'wb') as f:
                    f.write(resposta.content)
                return f"Sucesso: Imagem gerada e salva como {nome_arquivo} no projeto."
            else:
                return f"Erro na API de imagem: Status {resposta.status_code}"
        except Exception as e:
            return f"Erro ao gerar imagem: {str(e)}"
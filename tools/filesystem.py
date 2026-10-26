import os
import PyPDF2
import pandas as pd

class SecureWorkspace:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        if not os.path.exists(workspace_dir):
            os.makedirs(workspace_dir)

    def get_project_tree(self, relative_path=".") -> str:
        base_path = os.path.join(self.workspace_dir, relative_path)
        if not os.path.exists(base_path):
            return f"Erro: Caminho '{relative_path}' não existe."
        
        tree = []
        for root, dirs, files in os.walk(base_path):
            level = root.replace(base_path, '').count(os.sep)
            indent = ' ' * 4 * (level)
            tree.append(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                tree.append(f"{subindent}{f}")
        return "\n".join(tree)

    def read_file(self, relative_path: str) -> str:
        caminho = os.path.join(self.workspace_dir, relative_path)
        if not os.path.exists(caminho):
            return f"Erro: Arquivo '{relative_path}' não encontrado."
        
        extensao = caminho.lower().split('.')[-1]
        
        try:
            # Novo superpoder: Ler PDFs
            if extensao == 'pdf':
                texto = ""
                with open(caminho, 'rb') as f:
                    leitor = PyPDF2.PdfReader(f)
                    for pagina in leitor.pages:
                        extraido = pagina.extract_text()
                        if extraido: texto += extraido + "\n"
                return texto if texto.strip() else "PDF lido, mas nenhum texto detectável encontrado (pode ser uma imagem escaneada)."
                
            # Novo superpoder: Ler Planilhas (CSV e Excel)
            elif extensao in ['csv']:
                df = pd.read_csv(caminho)
                # Retornamos as 100 primeiras linhas para não estourar a memória da IA
                return f"Planilha CSV (Amostra das 100 primeiras linhas):\n{df.head(100).to_string()}"
                
            elif extensao in ['xlsx', 'xls']:
                df = pd.read_excel(caminho)
                return f"Planilha Excel (Amostra das 100 primeiras linhas):\n{df.head(100).to_string()}"
                
            # Leitura de arquivos de código/texto padrão
            else:
                with open(caminho, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            return f"Erro ao ler arquivo: {str(e)}"

    def write_file(self, relative_path: str, content: str) -> str:
        caminho = os.path.join(self.workspace_dir, relative_path)
        os.makedirs(os.path.dirname(caminho) or '.', exist_ok=True)
        try:
            with open(caminho, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Arquivo '{relative_path}' salvo com sucesso!"
        except Exception as e:
            return f"Erro ao escrever arquivo: {str(e)}"
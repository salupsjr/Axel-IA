import subprocess
import os

class SecureTerminal:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        if not os.path.exists(workspace_dir):
            os.makedirs(workspace_dir)

    def execute(self, command: str) -> str:
        try:
            # Executa direto, a trava de segurança agora fica na Web (app.py)
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=60 # Previne travamentos se o comando rodar em loop
            )
            saida = result.stdout + result.stderr
            return saida if saida.strip() else "Comando executado com sucesso (sem saída no terminal)."
        except subprocess.TimeoutExpired:
            return "Erro: O comando demorou muito para responder e foi cancelado pelo sistema."
        except Exception as e:
            return f"Erro ao executar comando: {str(e)}"
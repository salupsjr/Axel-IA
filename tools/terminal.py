import subprocess
import os

class SecureTerminal:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        if not os.path.exists(workspace_dir):
            os.makedirs(workspace_dir)

        # Lista de comandos inofensivos de leitura (Whitelist)
        self.safe_prefixes = [
            "dir", "ls", "pwd", "echo", "cd", "cat", "type", "whoami", "date",
            "python --version", "node -v", "npm -v", "pip list", "pip show", "git status", "git log"
        ]

    def is_safe_command(self, command: str) -> bool:
        """Verifica se o comando é inofensivo e pode rodar sem perturbar o usuário."""
        cmd_lower = command.strip().lower()
        
        # Bloqueia encadeamentos ou redirecionamentos destrutivos (>, |, &, ;)
        if any(char in cmd_lower for char in ['|', '>', '<', '&', ';']):
            return False 
        
        for prefix in self.safe_prefixes:
            if cmd_lower.startswith(prefix):
                return True
        return False

    def execute(self, command: str) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            saida = result.stdout + result.stderr
            return saida if saida.strip() else "Comando executado com sucesso (sem saída no terminal)."
        except subprocess.TimeoutExpired:
            return "Erro: O comando demorou muito para responder e foi cancelado pelo sistema."
        except Exception as e:
            return f"Erro ao executar comando: {str(e)}"
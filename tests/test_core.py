import os
import json
import pytest
from core.agent import BionicAgent
from core import database
from personas import SQUAD


@pytest.fixture
def agent():
    return BionicAgent(workspace_path="./workspace", api_key="fake-key-for-tests")


def test_appsec_bloqueia_env(agent):
    caminho, erro = agent._validar_caminho_seguro(".env")
    assert caminho is None
    assert "BLOQUEADO (AppSec)" in erro


def test_appsec_permite_env_example(agent):
    caminho, erro = agent._validar_caminho_seguro(".env.example")
    assert erro is None
    assert caminho.endswith(".env.example")


def test_appsec_bloqueia_path_traversal(agent):
    caminho, erro = agent._validar_caminho_seguro("../../Windows/System32/drivers/etc/hosts")
    assert caminho is None
    assert "BLOQUEADO (AppSec)" in erro


def test_appsec_bloqueia_pastas_internas(agent):
    for pasta in [".git/config", "venv/pyvenv.cfg", "__pycache__/test.pyc"]:
        caminho, erro = agent._validar_caminho_seguro(pasta)
        assert caminho is None
        assert "BLOQUEADO (AppSec)" in erro


def test_appsec_bloqueia_comandos_perigosos(agent):
    assert agent._comando_eh_proibido("rm -rf /") is True
    assert agent._comando_eh_proibido("type .env") is True
    assert agent._comando_eh_proibido("cat .env") is True
    assert agent._comando_eh_proibido("shutdown /s") is True
    assert agent._comando_eh_proibido("dir") is False


def test_ast_bloqueia_python_quebrado(agent):
    class FakeFunc:
        name = "write_file"
        arguments = json.dumps({"path": "workspace/teste_quebrado.py", "content": "def quebrado(:\n    pass"})

    class FakeCall:
        id = "call_test_1"
        function = FakeFunc()

    class FakeMsg:
        content = ""
        tool_calls = [FakeCall()]

    log_acoes = []
    agent._processar_tool_calls_interno(FakeMsg(), log_acoes)
    assert any("Impediu gravação de Python quebrado" in log for log in log_acoes)
    assert not os.path.exists("workspace/teste_quebrado.py")


def test_squad_tem_todas_as_personas():
    esperadas = {"AXEL_CORE", "ARCHITECT", "DEVELOPER", "AUDITOR_PJ", "ANALYST", "GROWTH", "ROUTINE", "CRITICO"}
    assert esperadas.issubset(set(SQUAD.keys()))


def test_database_historico_e_memoria(tmp_path, monkeypatch):
    db_teste = tmp_path / "test_axel.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_teste))

    database.init_db()
    database.salvar_mensagem("sessao_1", "user", "Olá Axel", especialista="AXEL_CORE")
    database.salvar_mensagem("sessao_1", "assistant", "Olá Jr!", especialista="AXEL_CORE", modelo="test-model")

    hist = database.buscar_historico("sessao_1", limite=5)
    assert len(hist) == 2
    assert hist[0]["role"] == "user"
    assert hist[1]["content"] == "Olá Jr!"

    database.salvar_memoria_db("Investimentos", "Carteira focada em dividendos e FIIs", "inv.md")
    res = database.buscar_memorias_relevantes("Como estão meus dividendos?")
    assert "dividendos" in res.lower()
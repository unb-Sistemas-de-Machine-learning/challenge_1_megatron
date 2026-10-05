from pathlib import Path

import pytest

from verdade_ou_fake.model_card import calcular_hash_artefato, montar_card, salvar_card
from verdade_ou_fake.modelo_producao import (
    ARQUIVO_PESOS,
    ModeloIndisponivel,
    localizar_modelo,
    preparar_modelo_de_producao,
)


def _criar_modelo(diretorio: Path) -> Path:
    diretorio.mkdir(parents=True)
    (diretorio / "config.json").write_text("{}")
    (diretorio / ARQUIVO_PESOS).write_bytes(b"pesos do modelo")
    return diretorio


def _criar_card(caminho: Path, pesos: Path, status: str = "producao") -> Path:
    card = montar_card(
        nome="bertimbau", tipo="bert_finetuned", commit="abc1234",
        dados={}, metricas={"f1_macro_same_source": 0.9},
        limiar_aprovacao={"f1_macro_same_source_minimo": 0.75, "queda_maxima_cross_source": 0.2},
        artefato_hash=calcular_hash_artefato(pesos),
        treinado_em="2026-10-05T10:00:00-03:00", treinado_por="scripts/treina_bert.py",
        status=status,
    )
    salvar_card(card, caminho)
    return caminho


def test_origem_que_e_diretorio_local_e_usada_sem_baixar(tmp_path):
    modelo = _criar_modelo(tmp_path / "bertimbau")

    def baixar(**kwargs):
        raise AssertionError("não deveria baixar")

    assert localizar_modelo(str(modelo), baixar=baixar) == modelo


def test_origem_que_e_repo_do_hub_e_baixada_sem_checkpoints(tmp_path):
    chamadas = []

    def baixar(**kwargs):
        chamadas.append(kwargs)
        return str(_criar_modelo(tmp_path / "cache"))

    caminho = localizar_modelo("equipe/bertimbau-saude", revisao="v1", baixar=baixar)

    assert caminho == tmp_path / "cache"
    assert chamadas[0]["repo_id"] == "equipe/bertimbau-saude"
    assert chamadas[0]["revision"] == "v1"
    assert "_checkpoints/*" in chamadas[0]["ignore_patterns"]


def test_diretorio_local_inexistente_que_nao_parece_repo_falha_com_mensagem(tmp_path):
    with pytest.raises(ModeloIndisponivel, match="não encontrado"):
        localizar_modelo(str(tmp_path / "nao_existe"), baixar=lambda **k: None)


def test_falha_no_download_vira_modelo_indisponivel():
    def baixar(**kwargs):
        raise OSError("sem rede")

    with pytest.raises(ModeloIndisponivel, match="sem rede"):
        localizar_modelo("equipe/bertimbau-saude", baixar=baixar)


def test_preparar_modelo_aceita_card_de_producao_com_hash_correto(tmp_path):
    modelo = _criar_modelo(tmp_path / "bertimbau")
    card = _criar_card(tmp_path / "bertimbau.json", modelo / ARQUIVO_PESOS)

    assert preparar_modelo_de_producao(str(modelo), card) == modelo


def test_preparar_modelo_recusa_card_em_staging(tmp_path):
    modelo = _criar_modelo(tmp_path / "bertimbau")
    card = _criar_card(tmp_path / "bertimbau.json", modelo / ARQUIVO_PESOS, status="staging")

    with pytest.raises(ModeloIndisponivel, match="staging"):
        preparar_modelo_de_producao(str(modelo), card)


def test_preparar_modelo_recusa_pesos_diferentes_do_card(tmp_path):
    modelo = _criar_modelo(tmp_path / "bertimbau")
    card = _criar_card(tmp_path / "bertimbau.json", modelo / ARQUIVO_PESOS)
    (modelo / ARQUIVO_PESOS).write_bytes(b"pesos retreinados sem atualizar o card")

    with pytest.raises(ModeloIndisponivel, match="[Hh]ash"):
        preparar_modelo_de_producao(str(modelo), card)

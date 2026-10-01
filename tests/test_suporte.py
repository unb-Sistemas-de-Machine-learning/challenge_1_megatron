import json
from pathlib import Path

import pytest

from verdade_ou_fake.suporte import LIMIAR_CONFIANCA, classificar_suporte

FIXTURES = Path(__file__).parent / "fixtures"


def carregar_casos() -> list[dict]:
    return json.loads((FIXTURES / "nli_casos.json").read_text(encoding="utf-8"))


def classificador_falso_para(caso: dict):
    """Simula o pipeline zero-shot devolvendo o rótulo vencedor já decidido pelo caso."""
    rotulo_vencedor = caso["rotulo_vencedor_simulado"]
    score_vencedor = caso["score_simulado"]

    def classificador(sequencia: str, rotulos: list[str]) -> dict:
        outro_rotulo = next(r for r in rotulos if r != rotulo_vencedor)
        return {
            "labels": [rotulo_vencedor, outro_rotulo],
            "scores": [score_vencedor, 1 - score_vencedor],
        }

    return classificador


@pytest.mark.parametrize("caso", carregar_casos(), ids=lambda c: c["descricao"])
def test_classifica_conforme_o_caso_da_fixture(caso):
    resultado = classificar_suporte(
        caso["resumo"], caso["alegacao"], classificador=classificador_falso_para(caso)
    )
    assert resultado == caso["esperado"]


def test_repassa_o_resumo_e_a_alegacao_para_o_classificador():
    capturado = {}

    def classificador_espiao(sequencia: str, rotulos: list[str]) -> dict:
        capturado["sequencia"] = sequencia
        capturado["rotulos"] = rotulos
        return {"labels": [rotulos[0], rotulos[1]], "scores": [0.9, 0.1]}

    classificar_suporte(
        "resumo do artigo", "ivermectina trata covid-19", classificador=classificador_espiao
    )

    assert capturado["sequencia"] == "resumo do artigo"
    assert any("ivermectina trata covid-19" in rotulo for rotulo in capturado["rotulos"])


def test_limiar_de_confianca_e_075():
    assert LIMIAR_CONFIANCA == 0.75


def test_resumo_vazio_e_nao_determinado_sem_chamar_o_classificador():
    def classificador_que_nao_deveria_ser_chamado(sequencia, rotulos):
        raise AssertionError("não deveria classificar um resumo vazio")

    resultado = classificar_suporte(
        "", "alegação qualquer", classificador=classificador_que_nao_deveria_ser_chamado
    )

    assert resultado == "nao_determinado"

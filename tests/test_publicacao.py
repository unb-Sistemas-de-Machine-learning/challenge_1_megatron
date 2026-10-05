import pytest

from publica_modelo import conferir_artefato
from publica_space import ARQUIVOS_DO_SPACE, conferir_card_de_producao, montar_pasta_space
from verdade_ou_fake.model_card import calcular_hash_artefato, montar_card, salvar_card


def _salvar_card(caminho, artefato_hash="0" * 64, status="staging"):
    salvar_card(
        montar_card(
            nome="bertimbau", tipo="bert_finetuned", commit="abc1234", dados={},
            metricas={"f1_macro_same_source": 0.9}, limiar_aprovacao={},
            artefato_hash=artefato_hash, treinado_em="2026-10-05T10:00:00-03:00",
            treinado_por="scripts/treina_bert.py", status=status,
        ),
        caminho,
    )
    return caminho


def test_publica_modelo_recusa_pesos_que_nao_batem_com_o_card(tmp_path):
    modelo = tmp_path / "bertimbau"
    modelo.mkdir()
    (modelo / "model.safetensors").write_bytes(b"pesos")
    card = _salvar_card(tmp_path / "bertimbau.json")

    with pytest.raises(ValueError, match="não correspondem"):
        conferir_artefato(modelo, card)


def test_publica_modelo_aceita_pesos_descritos_pelo_card(tmp_path):
    modelo = tmp_path / "bertimbau"
    modelo.mkdir()
    (modelo / "model.safetensors").write_bytes(b"pesos")
    card = _salvar_card(tmp_path / "bertimbau.json", calcular_hash_artefato(modelo / "model.safetensors"))

    assert conferir_artefato(modelo, card)["nome"] == "bertimbau"


def test_publica_space_recusa_card_em_staging(tmp_path):
    with pytest.raises(ValueError, match="staging"):
        conferir_card_de_producao(_salvar_card(tmp_path / "card.json"))


def test_publica_space_aceita_card_em_producao(tmp_path):
    conferir_card_de_producao(_salvar_card(tmp_path / "card.json", status="producao"))


def test_pasta_do_space_tem_o_necessario_e_nenhum_peso(tmp_path, request):
    raiz = request.config.rootpath
    montar_pasta_space(raiz, tmp_path)

    for relativo in ARQUIVOS_DO_SPACE:
        assert (tmp_path / relativo).exists(), relativo
    assert (tmp_path / "README.md").read_text(encoding="utf-8").startswith("---\n")
    assert "sdk: docker" in (tmp_path / "README.md").read_text(encoding="utf-8")
    assert not list(tmp_path.rglob("*.safetensors"))
    assert not list(tmp_path.rglob("__pycache__"))

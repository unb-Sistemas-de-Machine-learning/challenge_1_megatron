import hashlib
import json

import pytest

from publica_modelo import conferir_artefato
from publica_space import ARQUIVOS_DO_SPACE, conferir_base, montar_pasta_space
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


def _montar_raiz(raiz, sha256=None):
    for relativo in ARQUIVOS_DO_SPACE:
        alvo = raiz / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if "." in alvo.name:
            alvo.write_text("x", encoding="utf-8")
        else:
            alvo.mkdir(exist_ok=True)
            (alvo / "arquivo.txt").write_text("x", encoding="utf-8")
    base = raiz / "dados" / "base"
    base.mkdir(parents=True, exist_ok=True)
    conteudo = b'{"pmid": "1"}\n'
    (base / "pubmed.jsonl").write_bytes(conteudo)
    (base / "manifesto.json").write_text(
        json.dumps({"sha256": sha256 or hashlib.sha256(conteudo).hexdigest()}), encoding="utf-8"
    )
    return raiz


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


def test_publica_space_aceita_base_integra(tmp_path):
    conferir_base(_montar_raiz(tmp_path))


def test_publica_space_recusa_base_ausente(tmp_path):
    with pytest.raises(ValueError, match="incompleta"):
        conferir_base(tmp_path)


def test_publica_space_recusa_manifesto_ausente(tmp_path):
    raiz = _montar_raiz(tmp_path)
    (raiz / "dados" / "base" / "manifesto.json").unlink()
    with pytest.raises(ValueError, match="incompleta"):
        conferir_base(raiz)


def test_publica_space_recusa_sha256_divergente(tmp_path):
    with pytest.raises(ValueError, match="SHA-256"):
        conferir_base(_montar_raiz(tmp_path, sha256="0" * 64))


def test_publica_space_nao_depende_do_model_card(tmp_path):
    raiz = _montar_raiz(tmp_path)
    assert not (raiz / "modelos" / "cards" / "bertimbau.json").exists()
    conferir_base(raiz)


def test_pasta_do_space_tem_o_necessario_e_nenhum_peso(tmp_path):
    raiz = _montar_raiz(tmp_path / "raiz")
    (raiz / "src" / "__pycache__").mkdir()
    (raiz / "src" / "__pycache__" / "x.pyc").write_bytes(b"")
    destino = tmp_path / "space"
    destino.mkdir()
    montar_pasta_space(raiz, destino)

    for relativo in ARQUIVOS_DO_SPACE:
        assert (destino / relativo).exists(), relativo
    readme = (destino / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("---\n")
    assert "sdk: docker" in readme
    assert "app_port: 7860" in readme
    assert not list(destino.rglob("*.safetensors"))
    assert not list(destino.rglob("__pycache__"))

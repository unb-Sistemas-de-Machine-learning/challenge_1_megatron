from pathlib import Path

from verdade_ou_fake.model_card import montar_card, salvar_card
from verifica_gate import main


def _card(f1_same_source: float, tmp_path: Path) -> Path:
    card = montar_card(
        nome="baseline", tipo="tfidf_logreg", commit="abc1234",
        dados={"fontes": ["fakebr"], "hash_fakebr": "x" * 64, "hash_fakerecogna": None,
               "volume_treino": 280, "volume_teste": 70},
        metricas={"f1_macro_same_source": f1_same_source,
                  "f1_macro_cross_source_fakebr_para_fakerecogna": None,
                  "f1_macro_cross_source_fakerecogna_para_fakebr": None},
        limiar_aprovacao={"f1_macro_same_source_minimo": 0.75, "queda_maxima_cross_source": 0.20},
        artefato_hash="y" * 64, treinado_em="2026-10-01T14:30:00-03:00",
        treinado_por="scripts/treina_modelo.py",
    )
    caminho = tmp_path / "baseline.json"
    salvar_card(card, caminho)
    return caminho


def test_sai_com_codigo_zero_quando_aprova(tmp_path):
    caminho = _card(f1_same_source=0.81, tmp_path=tmp_path)
    assert main(str(caminho)) == 0


def test_sai_com_codigo_um_quando_reprova(tmp_path):
    caminho = _card(f1_same_source=0.50, tmp_path=tmp_path)
    assert main(str(caminho)) == 1

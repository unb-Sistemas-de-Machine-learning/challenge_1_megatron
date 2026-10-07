from pathlib import Path

from verdade_ou_fake.model_card import (
    aprovar_gate,
    calcular_hash_artefato,
    carregar_card,
    montar_card,
    salvar_card,
)


def test_hash_e_deterministico_para_o_mesmo_arquivo(tmp_path):
    arquivo = tmp_path / "modelo.joblib"
    arquivo.write_bytes(b"conteudo do modelo")
    assert calcular_hash_artefato(arquivo) == calcular_hash_artefato(arquivo)


def test_hash_muda_se_o_conteudo_mudar(tmp_path):
    arquivo = tmp_path / "modelo.joblib"
    arquivo.write_bytes(b"conteudo original")
    hash_original = calcular_hash_artefato(arquivo)
    arquivo.write_bytes(b"conteudo alterado")
    assert calcular_hash_artefato(arquivo) != hash_original


def _card_valido(**sobrescritas) -> dict:
    base = dict(
        nome="baseline",
        tipo="tfidf_logreg",
        commit="abc1234",
        dados={
            "fontes": ["fakebr"],
            "hash_fakebr": "x" * 64,
            "hash_fakerecogna": None,
            "volume_treino": 280,
            "volume_teste": 70,
        },
        metricas={
            "f1_macro_same_source": 0.81,
            "f1_macro_cross_source_fakebr_para_fakerecogna": None,
            "f1_macro_cross_source_fakerecogna_para_fakebr": None,
        },
        limiar_aprovacao={
            "f1_macro_same_source_minimo": 0.75,
            "queda_maxima_cross_source": 0.20,
        },
        artefato_hash="y" * 64,
        treinado_em="2026-10-01T14:30:00-03:00",
        treinado_por="scripts/treina_modelo.py",
    )
    base.update(sobrescritas)
    return montar_card(**base)


def test_montar_card_produz_status_staging_por_padrao():
    card = _card_valido()
    assert card["status"] == "staging"
    assert card["nome"] == "baseline"


def test_salva_e_recarrega_preservando_o_conteudo(tmp_path):
    card = _card_valido()
    caminho = tmp_path / "baseline.json"
    salvar_card(card, caminho)
    recarregado = carregar_card(caminho)
    assert recarregado == card


def test_aprova_quando_f1_acima_do_minimo_e_sem_queda_cross_source():
    card = _card_valido(
        metricas={
            "f1_macro_same_source": 0.81,
            "f1_macro_cross_source_fakebr_para_fakerecogna": 0.75,
            "f1_macro_cross_source_fakerecogna_para_fakebr": 0.70,
        }
    )
    assert aprovar_gate(card) is True


def test_reprova_quando_f1_same_source_abaixo_do_minimo():
    card = _card_valido(
        metricas={
            "f1_macro_same_source": 0.60,
            "f1_macro_cross_source_fakebr_para_fakerecogna": None,
            "f1_macro_cross_source_fakerecogna_para_fakebr": None,
        }
    )
    assert aprovar_gate(card) is False


def test_reprova_quando_queda_cross_source_excede_o_limiar():
    card = _card_valido(
        metricas={
            "f1_macro_same_source": 0.90,
            "f1_macro_cross_source_fakebr_para_fakerecogna": 0.50,
            "f1_macro_cross_source_fakerecogna_para_fakebr": 0.55,
        }
    )
    assert aprovar_gate(card) is False


def test_aprova_no_limite_exato_da_queda_permitida():
    card = _card_valido(
        metricas={
            "f1_macro_same_source": 0.80,
            "f1_macro_cross_source_fakebr_para_fakerecogna": 0.60,
            "f1_macro_cross_source_fakerecogna_para_fakebr": 0.60,
        }
    )
    assert aprovar_gate(card) is True


def test_aprova_sem_avaliar_cross_source_quando_metricas_sao_none():
    card = _card_valido(
        metricas={
            "f1_macro_same_source": 0.81,
            "f1_macro_cross_source_fakebr_para_fakerecogna": None,
            "f1_macro_cross_source_fakerecogna_para_fakebr": None,
        }
    )
    assert aprovar_gate(card) is True

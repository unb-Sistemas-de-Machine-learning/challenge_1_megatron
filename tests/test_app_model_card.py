from pathlib import Path

from verdade_ou_fake.model_card import montar_card, salvar_card, validar_modelo_para_producao


def _card_producao(artefato_hash: str) -> dict:
    return montar_card(
        nome="baseline",
        tipo="tfidf_logreg",
        commit="abc1234",
        dados={"fontes": ["fakebr"], "hash_fakebr": "x" * 64, "hash_fakerecogna": None,
               "volume_treino": 280, "volume_teste": 70},
        metricas={"f1_macro_same_source": 0.81,
                  "f1_macro_cross_source_fakebr_para_fakerecogna": None,
                  "f1_macro_cross_source_fakerecogna_para_fakebr": None},
        limiar_aprovacao={"f1_macro_same_source_minimo": 0.75, "queda_maxima_cross_source": 0.20},
        artefato_hash=artefato_hash,
        treinado_em="2026-10-01T14:30:00-03:00",
        treinado_por="scripts/treina_modelo.py",
        status="producao",
    )


def test_valida_com_sucesso_quando_hash_bate_e_status_e_producao(tmp_path):
    artefato = tmp_path / "baseline.joblib"
    artefato.write_bytes(b"conteudo do modelo")
    from verdade_ou_fake.model_card import calcular_hash_artefato
    hash_real = calcular_hash_artefato(artefato)

    card = _card_producao(hash_real)
    caminho_card = tmp_path / "baseline.json"
    salvar_card(card, caminho_card)

    ok, mensagem = validar_modelo_para_producao(caminho_card, artefato)
    assert ok is True


def test_reprova_quando_hash_nao_bate(tmp_path):
    artefato = tmp_path / "baseline.joblib"
    artefato.write_bytes(b"conteudo do modelo")

    card = _card_producao(artefato_hash="hash_errado" + "0" * 50)
    caminho_card = tmp_path / "baseline.json"
    salvar_card(card, caminho_card)

    ok, mensagem = validar_modelo_para_producao(caminho_card, artefato)
    assert ok is False
    assert "hash" in mensagem.lower()


def test_reprova_quando_status_nao_e_producao(tmp_path):
    artefato = tmp_path / "baseline.joblib"
    artefato.write_bytes(b"conteudo do modelo")
    from verdade_ou_fake.model_card import calcular_hash_artefato
    hash_real = calcular_hash_artefato(artefato)

    card = _card_producao(hash_real)
    card["status"] = "staging"
    caminho_card = tmp_path / "baseline.json"
    salvar_card(card, caminho_card)

    ok, mensagem = validar_modelo_para_producao(caminho_card, artefato)
    assert ok is False
    assert "status" in mensagem.lower() or "produção" in mensagem.lower()


def test_reprova_quando_card_nao_existe(tmp_path):
    ok, mensagem = validar_modelo_para_producao(tmp_path / "inexistente.json", tmp_path / "modelo.joblib")
    assert ok is False

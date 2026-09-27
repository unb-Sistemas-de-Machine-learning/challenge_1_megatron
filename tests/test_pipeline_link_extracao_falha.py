from verdade_ou_fake import pipeline


def test_analisar_link_devolve_none_quando_extracao_falha(monkeypatch):
    monkeypatch.setattr(pipeline, "extrair_noticia", lambda url: None)

    resultado = pipeline.analisar_link(
        "https://portal.exemplo.com/materia-com-paywall",
        modelo=None,
        vocabulario={},
    )

    assert resultado is None

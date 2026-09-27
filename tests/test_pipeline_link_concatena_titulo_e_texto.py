from verdade_ou_fake import pipeline
from verdade_ou_fake.tipos import Noticia, Veredito


def test_analisar_link_junta_titulo_e_texto_antes_de_analisar(monkeypatch):
    noticia = Noticia(
        url="https://portal.exemplo.com/materia",
        titulo="Estudo aponta cura",
        texto="Corpo da matéria com detalhes do estudo.",
        dominio="portal.exemplo.com",
    )
    monkeypatch.setattr(pipeline, "extrair_noticia", lambda url: noticia)

    textos_recebidos = []
    veredito_esperado = Veredito(
        rotulo="Não foi possível verificar",
        confianca="baixa",
        risco_textual=0.1,
        alegacao=None,
        evidencia=None,
        explicacao="explicação de teste",
    )

    def analisar_texto_espiao(texto, modelo, vocabulario, **kwargs):
        textos_recebidos.append(texto)
        return veredito_esperado

    monkeypatch.setattr(pipeline, "analisar_texto", analisar_texto_espiao)

    resultado = pipeline.analisar_link(noticia.url, modelo=None, vocabulario={})

    assert textos_recebidos == [f"{noticia.titulo}\n\n{noticia.texto}"]
    assert resultado is veredito_esperado

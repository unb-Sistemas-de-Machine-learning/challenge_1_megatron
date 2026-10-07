from pathlib import Path

from verdade_ou_fake.evidencia import parsear_artigos

FIXTURES = Path(__file__).parent / "fixtures"


def carregar_xml() -> str:
    return (FIXTURES / "pubmed_resposta.xml").read_text(encoding="utf-8")


def test_parseia_os_dois_artigos_da_resposta():
    artigos = parsear_artigos(carregar_xml())
    assert len(artigos) == 2
    assert artigos[0].pmid == "33473311"
    assert artigos[0].ano == 2021


def test_parseia_titulo_e_tipos_de_estudo():
    artigos = parsear_artigos(carregar_xml())
    assert "Ivermectin" in artigos[0].titulo
    assert "Meta-Analysis" in artigos[0].tipos_estudo
    assert artigos[1].tipos_estudo == ["Randomized Controlled Trial"]


def test_junta_as_secoes_do_resumo():
    artigos = parsear_artigos(carregar_xml())
    assert "Trial background." in artigos[1].resumo
    assert "No significant difference was found." in artigos[1].resumo


def test_xml_vazio_devolve_lista_vazia():
    assert parsear_artigos("<PubmedArticleSet></PubmedArticleSet>") == []

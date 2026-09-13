from pathlib import Path

from verdade_ou_fake.ingestao import extrair_de_html

FIXTURES = Path(__file__).parent / "fixtures"


def carregar_fixture(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


def test_extrai_o_corpo_da_materia():
    html = carregar_fixture("noticia_exemplo.html")
    noticia = extrair_de_html(html, "https://portal.exemplo.com/materia")
    assert noticia is not None
    assert "ivermectina" in noticia.texto.lower()
    assert "antiparasitário" in noticia.texto.lower()


def test_descarta_menu_banner_e_rodape():
    html = carregar_fixture("noticia_exemplo.html")
    noticia = extrair_de_html(html, "https://portal.exemplo.com/materia")
    assert noticia is not None
    texto = noticia.texto.lower()
    assert "aceite nossos cookies" not in texto
    assert "copyright" not in texto
    assert "leia também" not in texto


def test_guarda_o_dominio_de_origem():
    html = carregar_fixture("noticia_exemplo.html")
    noticia = extrair_de_html(html, "https://portal.exemplo.com/saude/materia")
    assert noticia is not None
    assert noticia.dominio == "portal.exemplo.com"


def test_html_sem_conteudo_devolve_none():
    noticia = extrair_de_html("<html><body></body></html>", "https://x.com/a")
    assert noticia is None

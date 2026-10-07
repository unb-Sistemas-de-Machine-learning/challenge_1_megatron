from verdade_ou_fake.tipos import Noticia
from verdade_ou_fake.tipos import Alegacao
from verdade_ou_fake.tipos import Artigo

def test_noticia_guarda_os_campos_extraidos():
    noticia = Noticia(
        url="https://exemplo.com/materia",
        titulo="Remédio milagroso",
        texto="Corpo da matéria.",
        dominio="exemplo.com",
    )
    assert noticia.dominio == "exemplo.com"
    assert noticia.titulo == "Remédio milagroso"


def test_alegacao_guarda_os_termos_nos_dois_idiomas():
    alegacao = Alegacao(
        medicamento_pt="ivermectina",
        medicamento_en="Ivermectin",
        condicao_pt="covid-19",
        condicao_en="COVID-19",
    )
    assert alegacao.medicamento_en == "Ivermectin"


def test_artigo_guarda_o_tipo_de_estudo():
    artigo = Artigo(
        pmid="12345",
        titulo="A randomized trial",
        resumo="Resumo do estudo.",
        tipos_estudo=["Randomized Controlled Trial"],
        ano=2021,
    )
    assert "Randomized Controlled Trial" in artigo.tipos_estudo

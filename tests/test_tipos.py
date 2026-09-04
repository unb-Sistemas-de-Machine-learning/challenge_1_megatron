from verdade_ou_fake.tipos import Noticia
from verdade_ou_fake.tipos import Alegacao
from verdade_ou_fake.tipos import Artigo
from verdade_ou_fake.tipos import Evidencia
from verdade_ou_fake.tipos import Veredito

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


def test_evidencia_sem_artigos_significa_nao_coberta():
    evidencia = Evidencia(cobertura="nao_cobre", forca="nenhuma", artigos=[])
    assert evidencia.artigos == []
    assert evidencia.cobertura == "nao_cobre"


def test_artigo_guarda_o_tipo_de_estudo():
    artigo = Artigo(
        pmid="12345",
        titulo="A randomized trial",
        resumo="Resumo do estudo.",
        tipos_estudo=["Randomized Controlled Trial"],
        ano=2021,
    )
    assert "Randomized Controlled Trial" in artigo.tipos_estudo


def test_veredito_carrega_a_explicacao_para_o_usuario():
    veredito = Veredito(
        rotulo="Não foi possível verificar",
        confianca="baixa",
        risco_textual=0.8,
        alegacao=None,
        evidencia=None,
        explicacao="Não identificamos medicamento e condição no texto.",
    )
    assert veredito.confianca == "baixa"

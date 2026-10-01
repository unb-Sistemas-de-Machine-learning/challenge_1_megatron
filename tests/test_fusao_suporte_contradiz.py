from verdade_ou_fake.fusao import fundir
from verdade_ou_fake.tipos import Alegacao, Evidencia

ALEGACAO = Alegacao(
    medicamento_pt="ivermectina",
    medicamento_en="Ivermectin",
    condicao_pt="covid-19",
    condicao_en="COVID-19",
)


def test_literatura_contradiz_a_alegacao():
    evidencia = Evidencia(cobertura="encontrada", forca="forte", artigos=[], suporte="contradiz")

    veredito = fundir(0.2, ALEGACAO, evidencia)

    assert veredito.rotulo == "Literatura contradiz a alegação"
    assert "contradiz" in veredito.explicacao.lower()
    assert "falso" not in veredito.rotulo.lower()


def test_confianca_alta_quando_contradicao_vem_de_evidencia_forte():
    evidencia = Evidencia(cobertura="encontrada", forca="forte", artigos=[], suporte="contradiz")

    veredito = fundir(0.2, ALEGACAO, evidencia)

    assert veredito.confianca == "alta"


def test_confianca_media_quando_contradicao_vem_de_evidencia_fraca():
    evidencia = Evidencia(cobertura="encontrada", forca="fraca", artigos=[], suporte="contradiz")

    veredito = fundir(0.2, ALEGACAO, evidencia)

    assert veredito.confianca == "media"


def test_contradicao_prevalece_mesmo_com_texto_sensacionalista():
    evidencia = Evidencia(cobertura="encontrada", forca="forte", artigos=[], suporte="contradiz")

    veredito = fundir(0.95, ALEGACAO, evidencia)

    assert veredito.rotulo == "Literatura contradiz a alegação"

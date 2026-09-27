from verdade_ou_fake.fusao import fundir
from verdade_ou_fake.tipos import Alegacao, Evidencia

ALEGACAO = Alegacao(
    medicamento_pt="metformina",
    medicamento_en="Metformin",
    condicao_pt="diabetes",
    condicao_en="Diabetes Mellitus",
)


def test_literatura_apoia_a_alegacao_com_texto_sobrio_e_confianca_alta():
    evidencia = Evidencia(cobertura="encontrada", forca="forte", artigos=[], suporte="apoia")

    veredito = fundir(0.2, ALEGACAO, evidencia)

    assert veredito.rotulo == "Literatura apoia a alegação"
    assert veredito.confianca == "alta"
    assert "apoia" in veredito.explicacao.lower()


def test_apoio_com_texto_sensacionalista_ainda_alerta_sobre_o_estilo():
    evidencia = Evidencia(cobertura="encontrada", forca="forte", artigos=[], suporte="apoia")

    veredito = fundir(0.9, ALEGACAO, evidencia)

    assert veredito.rotulo == "Existe literatura, mas o texto tem sinais de alerta"
    assert veredito.confianca == "media"

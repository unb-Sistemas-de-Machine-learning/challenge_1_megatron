from verdade_ou_fake.fusao import fundir
from verdade_ou_fake.tipos import Alegacao, Evidencia

ALEGACAO = Alegacao(
    medicamento_pt="canabidiol",
    medicamento_en="Cannabidiol",
    condicao_pt="enxaqueca",
    condicao_en="Migraine Disorders",
)


def test_literatura_com_resultados_conflitantes():
    evidencia = Evidencia(cobertura="encontrada", forca="moderada", artigos=[], suporte="conflitante")

    veredito = fundir(0.3, ALEGACAO, evidencia)

    assert veredito.rotulo == "Literatura tem resultados conflitantes sobre o tema"
    assert veredito.confianca == "baixa"
    assert "direções diferentes" in veredito.explicacao.lower()

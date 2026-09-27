from verdade_ou_fake.fusao import fundir
from verdade_ou_fake.tipos import Alegacao, Evidencia

ALEGACAO = Alegacao(
    medicamento_pt="ivermectina",
    medicamento_en="Ivermectin",
    condicao_pt="covid-19",
    condicao_en="COVID-19",
)


def test_nenhum_veredito_com_suporte_afirma_verdade_absoluta():
    combinacoes = [
        fundir(0.2, ALEGACAO, Evidencia("encontrada", "forte", [], suporte="apoia")),
        fundir(0.9, ALEGACAO, Evidencia("encontrada", "forte", [], suporte="apoia")),
        fundir(0.2, ALEGACAO, Evidencia("encontrada", "forte", [], suporte="contradiz")),
        fundir(0.2, ALEGACAO, Evidencia("encontrada", "fraca", [], suporte="contradiz")),
        fundir(0.2, ALEGACAO, Evidencia("encontrada", "moderada", [], suporte="conflitante")),
    ]
    for veredito in combinacoes:
        assert "comprovado" not in veredito.rotulo.lower()
        assert "garantido" not in veredito.rotulo.lower()
        assert "falso" not in veredito.rotulo.lower()

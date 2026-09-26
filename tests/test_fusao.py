from verdade_ou_fake.fusao import fundir
from verdade_ou_fake.tipos import Alegacao, Evidencia

ALEGACAO = Alegacao(
    medicamento_pt="ivermectina",
    medicamento_en="Ivermectin",
    condicao_pt="covid-19",
    condicao_en="COVID-19",
)
SEM_COBERTURA = Evidencia(cobertura="nao_cobre", forca="nenhuma", artigos=[])
COBERTURA_FORTE = Evidencia(cobertura="encontrada", forca="forte", artigos=[])
COBERTURA_FRACA = Evidencia(cobertura="encontrada", forca="fraca", artigos=[])


def test_sem_alegacao_extraida_nao_verifica():
    veredito = fundir(risco_textual=0.9, alegacao=None, evidencia=None)
    assert veredito.rotulo == "Não foi possível verificar"
    assert veredito.confianca == "baixa"


def test_sem_alegacao_ainda_reporta_o_risco_textual():
    veredito = fundir(risco_textual=0.9, alegacao=None, evidencia=None)
    assert veredito.risco_textual == 0.9
    assert "sinais de alerta" in veredito.explicacao.lower()


def test_literatura_ausente_nunca_afirma_que_e_falso():
    veredito = fundir(0.9, ALEGACAO, SEM_COBERTURA)
    assert veredito.rotulo == "Não foi possível verificar"
    assert "falso" not in veredito.rotulo.lower()
    assert "não encontramos" in veredito.explicacao.lower()


def test_literatura_forte_com_texto_sobrio_e_tema_com_respaldo():
    veredito = fundir(0.2, ALEGACAO, COBERTURA_FORTE)
    assert veredito.rotulo == "Tema com respaldo na literatura"
    assert veredito.confianca == "media"


def test_literatura_forte_com_texto_sensacionalista_alerta_exagero():
    veredito = fundir(0.9, ALEGACAO, COBERTURA_FORTE)
    assert veredito.rotulo == "Existe literatura, mas o texto tem sinais de alerta"
    assert veredito.confianca == "media"


def test_literatura_fraca_e_sinalizada_como_limitada():
    veredito = fundir(0.2, ALEGACAO, COBERTURA_FRACA)
    assert veredito.rotulo == "Literatura limitada sobre o tema"
    assert veredito.confianca == "baixa"


def test_veredito_carrega_a_alegacao_e_a_evidencia():
    veredito = fundir(0.5, ALEGACAO, COBERTURA_FORTE)
    assert veredito.alegacao == ALEGACAO
    assert veredito.evidencia == COBERTURA_FORTE


def test_nenhum_veredito_afirma_verdade_absoluta():
    combinacoes = [
        fundir(0.1, ALEGACAO, COBERTURA_FORTE),
        fundir(0.9, ALEGACAO, COBERTURA_FORTE),
        fundir(0.5, ALEGACAO, COBERTURA_FRACA),
        fundir(0.5, ALEGACAO, SEM_COBERTURA),
        fundir(0.5, None, None),
    ]
    for veredito in combinacoes:
        assert "comprovado" not in veredito.rotulo.lower()
        assert "garantido" not in veredito.rotulo.lower()

from verdade_ou_fake.fusao import fundir, icone_do_veredito
from verdade_ou_fake.tipos import Alegacao, Evidencia

ALEGACAO = Alegacao("vitamina C", "vitamin C", "gripe", "influenza")


def _icone(suporte, forca="forte"):
    ev = Evidencia("encontrada", forca, [], suporte=suporte)
    return icone_do_veredito(fundir(0.1, ALEGACAO, ev))


def test_contradiz_nunca_e_verde():
    assert _icone("contradiz") == "🔴"
    assert _icone("contradiz", forca="fraca") == "🔴"


def test_apoia_com_confianca_alta_e_verde():
    assert _icone("apoia") == "🟢"


def test_conflitante_e_amarelo():
    assert _icone("conflitante") == "🟡"


def test_nao_verificavel_e_cinza():
    assert icone_do_veredito(fundir(0.1, None, None)) == "⚪"
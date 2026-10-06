from verdade_ou_fake.fusao import fundir
from verdade_ou_fake.tipos import Alegacao, Evidencia

ALEGACAO = Alegacao("vitamina C", "vitamin C", "gripe", "influenza")


def _veredito(suporte, forca="forte", cobertura="cobre", risco=0.1):
    ev = Evidencia(cobertura, forca, [], suporte=suporte)
    return fundir(risco, ALEGACAO, ev)


def test_contradiz_nunca_e_verde():
    assert _veredito("contradiz").icone == "🔴"
    assert _veredito("contradiz", forca="fraca").icone == "🔴"


def test_apoia_com_confianca_alta_e_verde():
    assert _veredito("apoia").icone == "🟢"


def test_conflitante_e_amarelo():
    assert _veredito("conflitante").icone == "🟡"


def test_nao_verificavel_sem_alegacao_e_cinza():
    assert fundir(0.1, None, None).icone == "⚪"


def test_nao_cobre_ignora_suporte_residual():
    # fundir() retorna "Não foi possível verificar" antes de olhar suporte;
    # o ícone tem que acompanhar o rótulo, não a evidência residual.
    for suporte in ("contradiz", "conflitante", "apoia"):
        v = _veredito(suporte, cobertura="nao_cobre")
        assert v.rotulo == "Não foi possível verificar"
        assert v.icone == "⚪"
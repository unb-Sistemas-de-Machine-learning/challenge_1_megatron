from verdade_ou_fake.suporte import avaliar_evidencia
from verdade_ou_fake.tipos import Alegacao, Artigo, Evidencia

ALEGACAO = Alegacao(
    medicamento_pt="ivermectina",
    medicamento_en="Ivermectin",
    condicao_pt="covid-19",
    condicao_en="COVID-19",
)


def artigo(pmid: str, resumo: str = "resumo") -> Artigo:
    return Artigo(pmid=pmid, titulo="t", resumo=resumo, tipos_estudo=[], ano=2020)


def classificador_por_pmid(mapa: dict[str, str]):
    """Devolve um `classificar` falso: o suporte de cada artigo é decidido pelo pmid embutido no resumo."""

    def classificar(resumo: str, alegacao: str) -> str:
        return mapa[resumo]

    return classificar


def test_evidencia_sem_artigos_nao_chama_o_classificador():
    def classificador_que_nao_deveria_ser_chamado(resumo, alegacao):
        raise AssertionError("não deveria classificar sem artigos")

    evidencia = Evidencia(cobertura="nao_cobre", forca="nenhuma", artigos=[])
    resultado = avaliar_evidencia(
        ALEGACAO, evidencia, classificar=classificador_que_nao_deveria_ser_chamado
    )

    assert resultado.suporte == "nao_avaliado"
    assert resultado.artigos == []


def test_todos_os_artigos_apoiam_agrega_como_apoia():
    artigos = [artigo("1", "a"), artigo("2", "b")]
    evidencia = Evidencia(cobertura="encontrada", forca="forte", artigos=artigos)

    resultado = avaliar_evidencia(
        ALEGACAO, evidencia, classificar=classificador_por_pmid({"a": "apoia", "b": "apoia"})
    )

    assert resultado.suporte == "apoia"
    assert [a.suporte for a in resultado.artigos] == ["apoia", "apoia"]


def test_todos_os_artigos_contradizem_agrega_como_contradiz():
    artigos = [artigo("1", "a"), artigo("2", "b")]
    evidencia = Evidencia(cobertura="encontrada", forca="moderada", artigos=artigos)

    resultado = avaliar_evidencia(
        ALEGACAO,
        evidencia,
        classificar=classificador_por_pmid({"a": "contradiz", "b": "contradiz"}),
    )

    assert resultado.suporte == "contradiz"


def test_apoio_e_contradicao_misturados_agrega_como_conflitante():
    artigos = [artigo("1", "a"), artigo("2", "b")]
    evidencia = Evidencia(cobertura="encontrada", forca="forte", artigos=artigos)

    resultado = avaliar_evidencia(
        ALEGACAO, evidencia, classificar=classificador_por_pmid({"a": "apoia", "b": "contradiz"})
    )

    assert resultado.suporte == "conflitante"


def test_so_nao_determinado_agrega_como_nao_determinado():
    artigos = [artigo("1", "a"), artigo("2", "b")]
    evidencia = Evidencia(cobertura="encontrada", forca="fraca", artigos=artigos)

    resultado = avaliar_evidencia(
        ALEGACAO,
        evidencia,
        classificar=classificador_por_pmid({"a": "nao_determinado", "b": "nao_determinado"}),
    )

    assert resultado.suporte == "nao_determinado"


def test_apoio_junto_de_nao_determinado_agrega_como_apoia():
    artigos = [artigo("1", "a"), artigo("2", "b")]
    evidencia = Evidencia(cobertura="encontrada", forca="forte", artigos=artigos)

    resultado = avaliar_evidencia(
        ALEGACAO,
        evidencia,
        classificar=classificador_por_pmid({"a": "apoia", "b": "nao_determinado"}),
    )

    assert resultado.suporte == "apoia"


def test_nao_muta_a_evidencia_original():
    artigos = [artigo("1", "a")]
    evidencia = Evidencia(cobertura="encontrada", forca="forte", artigos=artigos)

    avaliar_evidencia(ALEGACAO, evidencia, classificar=classificador_por_pmid({"a": "apoia"}))

    assert evidencia.suporte == "nao_avaliado"
    assert evidencia.artigos[0].suporte == "nao_avaliado"

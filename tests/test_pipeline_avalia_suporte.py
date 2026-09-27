from dataclasses import replace
from pathlib import Path

from verdade_ou_fake.classificador import treinar
from verdade_ou_fake.pipeline import analisar_texto
from verdade_ou_fake.tipos import Artigo, Evidencia
from verdade_ou_fake.vocabulario import carregar_vocabulario

CAMINHO_VOCABULARIO = Path(__file__).parent.parent / "dados" / "vocabulario_seed.csv"

TEXTOS = [
    "URGENTE!!! Cura milagrosa escondida pelos médicos, compartilhe agora",
    "Estudo publicado avalia a eficácia do tratamento em ensaio clínico controlado",
]
ROTULOS = [1, 0]


def artigo(pmid: str) -> Artigo:
    return Artigo(pmid=pmid, titulo="t", resumo="r", tipos_estudo=[], ano=2020)


def test_avalia_suporte_e_chamado_com_a_evidencia_encontrada_e_o_resultado_chega_ao_veredito():
    chamadas = []

    def avaliar_suporte_espiao(alegacao, evidencia):
        chamadas.append((alegacao, evidencia))
        artigos_avaliados = [replace(a, suporte="contradiz") for a in evidencia.artigos]
        return replace(evidencia, artigos=artigos_avaliados, suporte="contradiz")

    veredito = analisar_texto(
        "Estudo sobre ivermectina no tratamento da covid-19.",
        modelo=treinar(TEXTOS, ROTULOS),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=lambda _alegacao: Evidencia(
            cobertura="encontrada", forca="forte", artigos=[artigo("1")]
        ),
        avaliar_suporte=avaliar_suporte_espiao,
    )

    assert len(chamadas) == 1
    assert veredito.evidencia.suporte == "contradiz"


def test_sem_par_nao_chama_avaliar_suporte():
    def avaliar_suporte_que_nao_deveria_ser_chamado(alegacao, evidencia):
        raise AssertionError("não deveria avaliar suporte sem alegação")

    veredito = analisar_texto(
        "Prefeitura anuncia novas obras na avenida central da cidade.",
        modelo=treinar(TEXTOS, ROTULOS),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=lambda _alegacao: Evidencia(cobertura="encontrada", forca="forte", artigos=[]),
        avaliar_suporte=avaliar_suporte_que_nao_deveria_ser_chamado,
    )

    assert veredito.alegacao is None

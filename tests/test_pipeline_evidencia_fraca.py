from pathlib import Path

from verdade_ou_fake.classificador import treinar
from verdade_ou_fake.pipeline import analisar_texto
from verdade_ou_fake.tipos import Evidencia
from verdade_ou_fake.vocabulario import carregar_vocabulario

CAMINHO_VOCABULARIO = Path(__file__).parent.parent / "dados" / "vocabulario_seed.csv"

TEXTOS = [
    "URGENTE!!! Cura milagrosa escondida pelos médicos, compartilhe agora",
    "Estudo publicado avalia a eficácia do tratamento em ensaio clínico controlado",
]
ROTULOS = [1, 0]


def busca_falsa_com_evidencia_fraca(_alegacao):
    return Evidencia(cobertura="encontrada", forca="fraca", artigos=[])


def test_evidencia_fraca_via_pipeline_resulta_em_literatura_limitada():
    veredito = analisar_texto(
        "Estudo sobre ivermectina no tratamento da covid-19.",
        modelo=treinar(TEXTOS, ROTULOS),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=busca_falsa_com_evidencia_fraca,
    )

    assert veredito.rotulo == "Literatura limitada sobre o tema"
    assert veredito.confianca == "baixa"

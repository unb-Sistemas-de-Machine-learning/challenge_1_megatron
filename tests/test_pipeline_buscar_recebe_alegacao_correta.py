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


def test_buscar_e_chamado_com_a_alegacao_extraida_do_texto():
    alegacoes_recebidas = []

    def busca_espia(alegacao):
        alegacoes_recebidas.append(alegacao)
        return Evidencia(cobertura="encontrada", forca="forte", artigos=[])

    analisar_texto(
        "Nova pesquisa sobre Metformina no tratamento da Hipertensão.",
        modelo=treinar(TEXTOS, ROTULOS),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=busca_espia,
    )

    assert len(alegacoes_recebidas) == 1
    assert alegacoes_recebidas[0].medicamento_en == "Metformin"
    assert alegacoes_recebidas[0].condicao_en == "Hypertension"

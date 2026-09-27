from pathlib import Path

from verdade_ou_fake.classificador import treinar
from verdade_ou_fake.pipeline import analisar_texto
from verdade_ou_fake.tipos import Evidencia
from verdade_ou_fake.vocabulario import carregar_vocabulario

CAMINHO_VOCABULARIO = Path(__file__).parent.parent / "dados" / "vocabulario_seed.csv"

TEXTOS = [
    "URGENTE!!! Cura milagrosa escondida pelos médicos, compartilhe agora",
    "MILAGRE! Remédio secreto elimina a doença em 3 dias sem efeito colateral",
    "Estudo publicado avalia a eficácia do tratamento em ensaio clínico controlado",
    "Pesquisa universitária analisa o uso do medicamento em pacientes internados",
]
ROTULOS = [1, 1, 0, 0]


def modelo_de_teste():
    return treinar(TEXTOS, ROTULOS)


def busca_falsa_com_evidencia(_alegacao):
    return Evidencia(cobertura="encontrada", forca="forte", artigos=[])


def busca_falsa_sem_evidencia(_alegacao):
    return Evidencia(cobertura="nao_cobre", forca="nenhuma", artigos=[])


def test_texto_com_par_conhecido_produz_veredito_com_alegacao():
    veredito = analisar_texto(
        "Estudo sobre ivermectina no tratamento da covid-19.",
        modelo=modelo_de_teste(),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=busca_falsa_com_evidencia,
    )
    assert veredito.alegacao is not None
    assert veredito.alegacao.medicamento_en == "Ivermectin"
    assert veredito.rotulo == "Tema com respaldo na literatura"


def test_texto_sem_par_nao_chega_a_buscar():
    chamadas = []

    def busca_espia(alegacao):
        chamadas.append(alegacao)
        return busca_falsa_com_evidencia(alegacao)

    veredito = analisar_texto(
        "Prefeitura anuncia novas obras na avenida central da cidade.",
        modelo=modelo_de_teste(),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=busca_espia,
    )
    assert chamadas == []
    assert veredito.rotulo == "Não foi possível verificar"


def test_sem_literatura_o_veredito_e_nao_verificavel():
    veredito = analisar_texto(
        "Estudo sobre ivermectina no tratamento da covid-19.",
        modelo=modelo_de_teste(),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=busca_falsa_sem_evidencia,
    )
    assert veredito.rotulo == "Não foi possível verificar"


def test_veredito_sempre_traz_risco_textual_valido():
    veredito = analisar_texto(
        "Estudo sobre metformina e diabetes.",
        modelo=modelo_de_teste(),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=busca_falsa_com_evidencia,
    )
    assert 0.0 <= veredito.risco_textual <= 1.0

from pathlib import Path

from verdade_ou_fake.classificador import treinar
from verdade_ou_fake.pipeline import analisar_link, analisar_texto
from verdade_ou_fake.tipos import Evidencia, Noticia
from verdade_ou_fake.vocabulario import carregar_vocabulario

CAMINHO_VOCABULARIO = Path(__file__).parent.parent / "dados" / "vocabulario_seed.csv"

TEXTOS = [
    "URGENTE!!! Cura milagrosa escondida pelos médicos, compartilhe agora",
    "Estudo publicado avalia a eficácia do tratamento em ensaio clínico controlado",
]
ROTULOS = [1, 0]


def busca_falsa_com_evidencia(_alegacao):
    return Evidencia(cobertura="encontrada", forca="forte", artigos=[])


def test_calcular_risco_injetavel_substitui_o_modelo_sklearn():
    def risco_falso(texto: str) -> float:
        return 0.42

    veredito = analisar_texto(
        "Estudo sobre metformina e diabetes.",
        modelo=None,
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=busca_falsa_com_evidencia,
        calcular_risco=risco_falso,
    )

    assert veredito.risco_textual == 0.42


def test_sem_calcular_risco_usa_o_modelo_sklearn_como_antes():
    veredito = analisar_texto(
        "Estudo sobre metformina e diabetes.",
        modelo=treinar(TEXTOS, ROTULOS),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        buscar=busca_falsa_com_evidencia,
    )

    assert 0.0 <= veredito.risco_textual <= 1.0


def test_analisar_link_repassa_calcular_risco(monkeypatch):
    noticia = Noticia(
        url="https://portal.exemplo.com/materia",
        titulo="Título",
        texto="Estudo sobre metformina e diabetes.",
        dominio="portal.exemplo.com",
    )
    from verdade_ou_fake import pipeline

    monkeypatch.setattr(pipeline, "extrair_noticia", lambda url: noticia)

    veredito = pipeline.analisar_link(
        noticia.url,
        modelo=None,
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
        calcular_risco=lambda texto: 0.77,
    )

    assert veredito.risco_textual == 0.77

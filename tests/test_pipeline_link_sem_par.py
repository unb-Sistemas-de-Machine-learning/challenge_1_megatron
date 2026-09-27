from pathlib import Path

from verdade_ou_fake import pipeline
from verdade_ou_fake.classificador import treinar
from verdade_ou_fake.tipos import Noticia
from verdade_ou_fake.vocabulario import carregar_vocabulario

CAMINHO_VOCABULARIO = Path(__file__).parent.parent / "dados" / "vocabulario_seed.csv"

TEXTOS = [
    "URGENTE!!! Cura milagrosa escondida pelos médicos, compartilhe agora",
    "Estudo publicado avalia a eficácia do tratamento em ensaio clínico controlado",
]
ROTULOS = [1, 0]


def test_analisar_link_sem_par_e_nao_verificavel(monkeypatch):
    noticia = Noticia(
        url="https://portal.exemplo.com/politica/materia",
        titulo="Prefeitura anuncia obras",
        texto="Prefeitura anuncia novas obras na avenida central da cidade.",
        dominio="portal.exemplo.com",
    )
    monkeypatch.setattr(pipeline, "extrair_noticia", lambda url: noticia)

    veredito = pipeline.analisar_link(
        noticia.url,
        modelo=treinar(TEXTOS, ROTULOS),
        vocabulario=carregar_vocabulario(CAMINHO_VOCABULARIO),
    )

    assert veredito is not None
    assert veredito.alegacao is None
    assert veredito.rotulo == "Não foi possível verificar"

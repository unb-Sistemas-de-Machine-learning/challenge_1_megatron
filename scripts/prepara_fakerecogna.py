"""Gera o recorte de saúde do FakeRecogna, reextraindo o texto original.

O FakeRecogna (recogna-nlp/FakeRecogna, Hugging Face, MIT) traz o texto da
notícia já lematizado pelos autores originais — inutilizável para treino
junto com o Fake.br (texto natural), porque o modelo aprenderia a diferença
de registro textual entre os dois datasets em vez de desinformação. Por
isso este script usa a tabela só como índice (URL + rótulo) e reextrai o
texto real via `ingestao.extrair_noticia`, a mesma função que já serve a
etapa [0] do pipeline.

Uso: python scripts/prepara_fakerecogna.py
"""

from collections.abc import Callable

import pandas as pd

from verdade_ou_fake.tipos import Noticia

ExtratorDeNoticia = Callable[[str], "Noticia | None"]

CATEGORIA_SAUDE = "saúde"


def ler_fakerecogna(caminho_parquet) -> pd.DataFrame:
    """Lê o parquet do FakeRecogna, mantendo só as colunas usadas pelo recorte."""
    df = pd.read_parquet(caminho_parquet)
    return df[["Titulo", "Noticia", "Categoria", "URL", "Classe"]]


def filtrar_categoria_saude(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém só as linhas de categoria 'saúde'."""
    return df[df["Categoria"] == CATEGORIA_SAUDE].copy()


def reextrair_textos(df: pd.DataFrame, extrair: ExtratorDeNoticia) -> pd.DataFrame:
    """Reextrai o texto original de cada URL, descartando as que falharem.

    O campo `Noticia` do FakeRecogna vem lematizado pelos autores originais
    e não é usado — só a URL e a Classe (rótulo) servem de índice. Isso evita
    que o modelo aprenda a diferença de registro textual entre o Fake.br
    (texto natural) e o FakeRecogna, em vez de sinal de desinformação.

    Mapeamento de rótulo: no FakeRecogna, `Classe == 0.0` significa "fake" e
    `Classe == 1.0` significa "real" — invertido em relação à convenção do
    projeto (`rotulo == 1` é desinformação, `rotulo == 0` é legítima). Por
    isso `rotulo = 1 - int(Classe)`.
    """
    linhas = []
    for _, linha in df.iterrows():
        noticia = extrair(linha["URL"])
        if noticia is None:
            continue
        linhas.append(
            {
                "id_par": f"fakerecogna-{len(linhas)}",
                "texto": noticia.texto,
                "rotulo": 1 - int(linha["Classe"]),
                "categoria": linha["Categoria"],
                "fonte": "fakerecogna",
            }
        )
    return pd.DataFrame(linhas, columns=["id_par", "texto", "rotulo", "categoria", "fonte"])


def taxa_de_extracao(total: int, sucesso: int) -> float:
    """Percentual de URLs que renderam texto aproveitável."""
    if total == 0:
        return 0.0
    return sucesso / total

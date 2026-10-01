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

import pandas as pd

CATEGORIA_SAUDE = "saúde"


def ler_fakerecogna(caminho_parquet) -> pd.DataFrame:
    """Lê o parquet do FakeRecogna, mantendo só as colunas usadas pelo recorte."""
    df = pd.read_parquet(caminho_parquet)
    return df[["Titulo", "Noticia", "Categoria", "URL", "Classe"]]


def filtrar_categoria_saude(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém só as linhas de categoria 'saúde'."""
    return df[df["Categoria"] == CATEGORIA_SAUDE].copy()

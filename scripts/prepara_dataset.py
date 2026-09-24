"""Extrai o recorte de saúde do corpus de notícias em português.

O corpus base (Fake.br) é de domínio geral. Este script seleciona as notícias
que mencionam algum medicamento ou condição do nosso vocabulário, produzindo o
dataset de treino da Camada 1.

Uso: python scripts/prepara_dataset.py
"""

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from verdade_ou_fake.vocabulario import carregar_vocabulario, normalizar

RAIZ = Path(__file__).parent.parent
CAMINHO_VOCABULARIO = RAIZ / "dados" / "vocabulario_seed.csv"
CAMINHO_SAIDA = RAIZ / "dados" / "processed" / "saude_ptbr.csv"


def termos_de_saude(caminho_vocabulario: Path) -> set[str]:
    """Devolve todos os termos em português do vocabulário, normalizados."""
    vocabulario = carregar_vocabulario(caminho_vocabulario)
    return {
        termo_pt
        for termos in vocabulario.values()
        for termo_pt, _ in termos
    }


def filtrar_saude(df: pd.DataFrame, coluna_texto: str, termos: set[str]) -> pd.DataFrame:
    """Mantém as linhas cujo texto menciona ao menos um termo de saúde.

    O casamento usa fronteira de palavra para não capturar termos contidos em
    outras palavras.
    """
    padrao = "|".join(r"\b" + re.escape(termo) + r"\b" for termo in termos)
    normalizados = df[coluna_texto].astype(str).map(normalizar)
    return df[normalizados.str.contains(padrao, regex=True, na=False)].copy()


def main() -> None:
    from datasets import load_dataset

    # ATENÇÃO: ajuste os nomes das colunas conforme o que você viu no Passo 1.
    coluna_texto = "text"
    coluna_rotulo = "label"

    conjunto = load_dataset("fake-news-UFG/fakebr", trust_remote_code=True)["train"]
    df = conjunto.to_pandas()
    print(f"Corpus completo: {len(df)} notícias")

    recorte = filtrar_saude(df, coluna_texto, termos_de_saude(CAMINHO_VOCABULARIO))
    print(f"Recorte de saúde: {len(recorte)} notícias")
    print(recorte[coluna_rotulo].value_counts())

    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    recorte.to_csv(CAMINHO_SAIDA, index=False)
    print(f"Salvo em {CAMINHO_SAIDA}")


if __name__ == "__main__":
    main()
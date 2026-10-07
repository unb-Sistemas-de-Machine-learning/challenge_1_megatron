import hashlib
import sys
from collections.abc import Callable
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.ingestao import extrair_noticia
from verdade_ou_fake.tipos import Noticia

ExtratorDeNoticia = Callable[[str], "Noticia | None"]

CATEGORIA_SAUDE = "saúde"

URL_PARQUET = "https://huggingface.co/api/datasets/recogna-nlp/FakeRecogna/parquet/default/train/0.parquet"
CAMINHO_PARQUET_LOCAL = RAIZ / "dados" / "raw" / "fakerecogna.parquet"
CAMINHO_SAIDA = RAIZ / "dados" / "processed" / "saude_fakerecogna.csv"


def ler_fakerecogna(caminho_parquet) -> pd.DataFrame:
    df = pd.read_parquet(caminho_parquet)
    colunas_esperadas = ["Titulo", "Noticia", "Categoria", "URL", "Classe"]
    try:
        return df[colunas_esperadas]
    except KeyError as e:
        raise KeyError(
            f"Schema inesperado em {caminho_parquet} (FakeRecogna) — colunas "
            f"esperadas {colunas_esperadas} não encontradas: {e}"
        ) from e


def filtrar_categoria_saude(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["Categoria"] == CATEGORIA_SAUDE].copy()


def reextrair_textos(df: pd.DataFrame, extrair: ExtratorDeNoticia) -> pd.DataFrame:
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
    if total == 0:
        return 0.0
    return sucesso / total


def impressao_digital_parquet(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def main() -> None:
    import requests

    CAMINHO_PARQUET_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    if not CAMINHO_PARQUET_LOCAL.exists():
        print(f"Baixando {URL_PARQUET}")
        resposta = requests.get(URL_PARQUET, timeout=120)
        resposta.raise_for_status()
        CAMINHO_PARQUET_LOCAL.write_bytes(resposta.content)

    hash_parquet = impressao_digital_parquet(CAMINHO_PARQUET_LOCAL)
    print(f"Hash do parquet: {hash_parquet}")

    df = filtrar_categoria_saude(ler_fakerecogna(CAMINHO_PARQUET_LOCAL))
    print(f"Notícias de saúde no FakeRecogna: {len(df)}")

    resultado = reextrair_textos(df, extrair=extrair_noticia)
    taxa = taxa_de_extracao(total=len(df), sucesso=len(resultado))
    print(f"Taxa de extração bem-sucedida: {taxa:.1%} ({len(resultado)}/{len(df)})")

    if len(resultado) == 0:
        print(
            "Erro: Nenhuma notícia foi extraída com sucesso — abortando sem "
            "sobrescrever a saída. Verifique a conectividade de rede e se o "
            "schema do FakeRecogna mudou."
        )
        sys.exit(1)

    print(resultado["rotulo"].value_counts().to_string(), "\n")

    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    resultado.to_csv(CAMINHO_SAIDA, index=False)
    print(f"Salvo em {CAMINHO_SAIDA}")


if __name__ == "__main__":
    main()

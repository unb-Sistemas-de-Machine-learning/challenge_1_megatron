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
    """Lê o parquet do FakeRecogna, mantendo só as colunas usadas pelo recorte."""
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


def impressao_digital_parquet(caminho: Path) -> str:
    """SHA-256 do conteúdo do parquet, para registrar no model card."""
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

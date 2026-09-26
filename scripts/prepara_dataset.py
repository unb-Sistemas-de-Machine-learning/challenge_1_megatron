"""Extrai o recorte de saúde do corpus de notícias em português.

O corpus base (Fake.br) é de domínio geral. Este script seleciona as notícias
que mencionam algum medicamento ou condição do nosso vocabulário, produzindo o
dataset de treino da Camada 1.

O corpus é baixado direto do repositório oficial no GitHub, fixado em um
commit, e verificado por uma impressão digital do conteúdo. Não usamos o
espelho do Hugging Face (`fake-news-UFG/fakebr`): ele é só um script de carga,
e a biblioteca `datasets` deixou de executar scripts na versão 4.0.

Uso: python scripts/prepara_dataset.py [--corpus PASTA_LOCAL]
"""

import argparse
import hashlib
import io
import re
import shutil
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from verdade_ou_fake.vocabulario import carregar_vocabulario, normalizar

RAIZ = Path(__file__).parent.parent
CAMINHO_VOCABULARIO = RAIZ / "dados" / "vocabulario_seed.csv"
CAMINHO_SAIDA = RAIZ / "dados" / "processed" / "saude_ptbr.csv"
DIRETORIO_FAKEBR = RAIZ / "dados" / "raw" / "fakebr"

# Commit fixo do repositório oficial: o corpus não muda embaixo de nós.
FAKEBR_COMMIT = "780f5516c4ae070761632d98ac3368f3ded09d35"
URL_FAKEBR = f"https://github.com/roneysco/Fake.br-Corpus/archive/{FAKEBR_COMMIT}.zip"

# SHA-256 do conteúdo dos arquivos usados (não do .zip, cuja compressão o
# GitHub pode mudar sem aviso). Calculado com `impressao_digital`.
IMPRESSAO_DIGITAL_FAKEBR = "ce86b8f8d74ec6086a7a9d0018e2e681ea022d88560ac5aaccc914e383df7d29"

# Convenção do projeto: 1 = desinformação, 0 = legítima.
ROTULOS = {"fake": 1, "true": 0}

# Versão em que cada par fake/true foi truncado ao tamanho do texto menor.
# Nos textos completos as verdadeiras são ~6x mais longas, e o modelo
# aprenderia "texto longo = verdadeiro" em vez do estilo de escrita.
VERSAO_TEXTOS = "size_normalized_texts"
LINHA_CATEGORIA = 2


def _arquivos_do_corpus(diretorio: Path) -> list[Path]:
    """Arquivos que o recorte usa: os textos e os metadados de cada notícia."""
    padroes = [f"{VERSAO_TEXTOS}/{rotulo}/*.txt" for rotulo in ROTULOS]
    padroes += [f"full_texts/{rotulo}-meta-information/*.txt" for rotulo in ROTULOS]
    return sorted(
        (arquivo for padrao in padroes for arquivo in diretorio.glob(padrao)),
        key=lambda arquivo: arquivo.relative_to(diretorio).as_posix(),
    )


def impressao_digital(diretorio: Path) -> str:
    """SHA-256 dos caminhos e conteúdos dos arquivos do corpus."""
    hash_ = hashlib.sha256()
    for arquivo in _arquivos_do_corpus(diretorio):
        hash_.update(arquivo.relative_to(diretorio).as_posix().encode("utf-8") + b"\0")
        hash_.update(arquivo.read_bytes() + b"\0")
    return hash_.hexdigest()


def verificar_integridade(diretorio: Path, esperada: str) -> None:
    """Falha se o corpus em disco não for exatamente o esperado."""
    obtida = impressao_digital(diretorio)
    if obtida != esperada:
        raise ValueError(
            f"A impressão digital do corpus em {diretorio} não confere.\n"
            f"  esperada: {esperada}\n  obtida:   {obtida}\n"
            "Apague a pasta e rode de novo para baixar o corpus fixado."
        )


def _ler_texto(caminho: Path) -> str:
    """Lê em UTF-8 removendo o BOM e as quebras de linha do Windows."""
    return caminho.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()


def _categoria(caminho_meta: Path) -> str:
    """Categoria da notícia (3ª linha do arquivo de metadados).

    O Fake.br tem inconsistências: os pares 697 e 1468 da versão normalizada
    não têm metadados. O texto e o rótulo continuam válidos, então a notícia
    é mantida com categoria "desconhecida".
    """
    if not caminho_meta.exists():
        return "desconhecida"
    # Sem strip() no arquivo inteiro: a 1ª linha (autor) pode vir em branco e
    # apagá-la deslocaria todas as outras.
    linhas = caminho_meta.read_text(encoding="utf-8-sig").splitlines()
    return linhas[LINHA_CATEGORIA].strip()


def ler_fakebr(diretorio: Path) -> pd.DataFrame:
    """Lê o Fake.br já extraído.

    Devolve colunas id_par, texto, rotulo e categoria. O id_par liga cada
    notícia falsa à verdadeira de mesmo assunto (fake/1.txt ↔ true/1.txt).
    """
    linhas = []
    for nome_rotulo, rotulo in ROTULOS.items():
        pasta_textos = diretorio / VERSAO_TEXTOS / nome_rotulo
        pasta_meta = diretorio / "full_texts" / f"{nome_rotulo}-meta-information"
        for arquivo in sorted(pasta_textos.glob("*.txt"), key=lambda a: int(a.stem)):
            linhas.append(
                {
                    "id_par": arquivo.stem,
                    "texto": _ler_texto(arquivo),
                    "rotulo": rotulo,
                    "categoria": _categoria(pasta_meta / f"{arquivo.stem}-meta.txt"),
                }
            )
    return pd.DataFrame(linhas, columns=["id_par", "texto", "rotulo", "categoria"])


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


def completar_pares(recorte: pd.DataFrame, corpus: pd.DataFrame) -> pd.DataFrame:
    """Devolve os pares inteiros de todas as notícias do recorte.

    Basta uma das metades mencionar saúde para o par entrar. Assim o recorte
    fica balanceado entre as classes e as duas notícias de um mesmo assunto
    ficam juntas, o que permite dividir treino e teste por par sem vazamento.
    """
    return corpus[corpus["id_par"].isin(recorte["id_par"])].copy()


def baixar_fakebr(destino: Path) -> None:
    """Baixa o repositório no commit fixado e extrai só as pastas usadas."""
    print(f"Baixando {URL_FAKEBR}")
    resposta = requests.get(URL_FAKEBR, timeout=120)
    resposta.raise_for_status()

    prefixo = f"Fake.br-Corpus-{FAKEBR_COMMIT}/"
    temporario = destino.with_name(destino.name + ".tmp")
    shutil.rmtree(temporario, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(resposta.content)) as pacote:
        for membro in pacote.infolist():
            relativo = membro.filename.removeprefix(prefixo)
            if membro.is_dir() or not relativo.startswith((f"{VERSAO_TEXTOS}/", "full_texts/")):
                continue
            if ".." in Path(relativo).parts:
                raise ValueError(f"Caminho suspeito no pacote: {membro.filename}")
            alvo = temporario / relativo
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_bytes(pacote.read(membro))

    shutil.rmtree(destino, ignore_errors=True)
    temporario.rename(destino)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--corpus",
        type=Path,
        help="pasta com o Fake.br já extraído (padrão: baixa em dados/raw/fakebr)",
    )
    args = parser.parse_args()

    diretorio = args.corpus or DIRETORIO_FAKEBR
    if not diretorio.exists():
        diretorio.parent.mkdir(parents=True, exist_ok=True)
        baixar_fakebr(diretorio)
    verificar_integridade(diretorio, IMPRESSAO_DIGITAL_FAKEBR)

    corpus = ler_fakebr(diretorio)
    print(f"Corpus completo: {len(corpus)} notícias")
    print(corpus["rotulo"].value_counts().to_string(), "\n")

    mencionam = filtrar_saude(corpus, "texto", termos_de_saude(CAMINHO_VOCABULARIO))
    recorte = completar_pares(mencionam, corpus)
    print(f"Notícias que mencionam termo de saúde: {len(mencionam)}")
    print(f"Recorte de saúde (pares completos): {len(recorte)} notícias, "
          f"{recorte['id_par'].nunique()} pares")
    print(recorte["rotulo"].value_counts().to_string(), "\n")
    print(recorte["categoria"].value_counts().to_string())

    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    recorte.to_csv(CAMINHO_SAIDA, index=False)
    print(f"\nSalvo em {CAMINHO_SAIDA}")


if __name__ == "__main__":
    main()

import csv
import re
import unicodedata
from pathlib import Path

from verdade_ou_fake.tipos import Alegacao


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower()


def carregar_vocabulario(caminho: Path) -> dict[str, list[tuple[str, str]]]:
    vocabulario: dict[str, list[tuple[str, str]]] = {"medicamento": [], "condicao": []}
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            tipo = linha["tipo"]
            if tipo in vocabulario:
                vocabulario[tipo].append((normalizar(linha["termo_pt"]), linha["termo_en"]))
    return vocabulario


def _primeiro_termo_presente(
    texto_normalizado: str, termos: list[tuple[str, str]]
) -> tuple[str, str] | None:
    for termo_pt, termo_en in sorted(termos, key=lambda par: -len(par[0])):
        padrao = r"\b" + re.escape(termo_pt) + r"\b"
        if re.search(padrao, texto_normalizado):
            return termo_pt, termo_en
    return None


def extrair_alegacao(texto: str, vocabulario: dict[str, list[tuple[str, str]]]) -> Alegacao | None:
    texto_normalizado = normalizar(texto)

    medicamento = _primeiro_termo_presente(texto_normalizado, vocabulario["medicamento"])
    condicao = _primeiro_termo_presente(texto_normalizado, vocabulario["condicao"])

    if medicamento is None or condicao is None:
        return None

    return Alegacao(
        medicamento_pt=medicamento[0],
        medicamento_en=medicamento[1],
        condicao_pt=condicao[0],
        condicao_en=condicao[1],
    )

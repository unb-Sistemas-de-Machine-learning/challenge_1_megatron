"""Etapa [2a] — identifica o par medicamento + condição no texto da notícia.

Usa casamento por dicionário controlado em vez de um modelo de NER: o domínio
é fechado (medicamentos e doenças têm nomes oficiais) e o dicionário é
auditável, o que um modelo treinado não seria.
"""

import csv
import re
import unicodedata
from pathlib import Path

from verdade_ou_fake.tipos import Alegacao


def normalizar(texto: str) -> str:
    """Remove acentos e coloca em minúsculas, para casar 'Hipertensão' com 'hipertensao'."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower()


def carregar_vocabulario(caminho: Path) -> dict[str, list[tuple[str, str]]]:
    """Lê o CSV e agrupa os termos por tipo.

    Devolve {"medicamento": [(termo_pt, termo_en), ...], "condicao": [...]}.
    Os termos em português vêm normalizados; os em inglês, como estão.
    """
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
    """Devolve o primeiro par (pt, en) cujo termo aparece como palavra inteira.

    Os termos são ordenados do mais longo para o mais curto para que
    'vitamina d' seja testado antes de eventuais termos contidos nele.
    """
    for termo_pt, termo_en in sorted(termos, key=lambda par: -len(par[0])):
        padrao = r"\b" + re.escape(termo_pt) + r"\b"
        if re.search(padrao, texto_normalizado):
            return termo_pt, termo_en
    return None


def extrair_alegacao(texto: str, vocabulario: dict[str, list[tuple[str, str]]]) -> Alegacao | None:
    """Procura um medicamento e uma condição no texto.

    Devolve None se faltar qualquer um dos dois — sem o par não há o que
    consultar no PubMed.
    """
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
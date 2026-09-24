"""Etapa [0] — transforma o link de uma notícia em texto limpo.

A extração é dividida em duas funções: `extrair_de_html` é pura e testável,
`extrair_noticia` acrescenta o download. Essa separação é o que permite testar
sem internet.
"""

from urllib.parse import urlparse

import requests
import trafilatura

from verdade_ou_fake.tipos import Noticia

TAMANHO_MINIMO = 100
TIMEOUT_SEGUNDOS = 15


def extrair_de_html(html: str, url: str) -> Noticia | None:
    """Extrai o conteúdo principal de uma página já baixada.

    Devolve None quando não há corpo de texto aproveitável — página vazia,
    paywall ou layout que o trafilatura não reconhece.
    """
    texto = trafilatura.extract(html, include_comments=False, include_tables=False)
    if not texto or len(texto) < TAMANHO_MINIMO:
        return None

    metadados = trafilatura.extract_metadata(html)
    titulo = metadados.title if metadados and metadados.title else ""

    return Noticia(
        url=url,
        titulo=titulo,
        texto=texto,
        dominio=urlparse(url).netloc,
    )


def extrair_noticia(url: str) -> Noticia | None:
    """Baixa a página e extrai o conteúdo. Devolve None se o download falhar."""
    try:
        resposta = requests.get(
            url,
            timeout=TIMEOUT_SEGUNDOS,
            headers={"User-Agent": "VerdadeOuFake/0.1 (projeto academico UnB)"},
        )
        resposta.raise_for_status()
    except requests.RequestException:
        return None

    return extrair_de_html(resposta.text, url)

"""Etapa [0] — transforma o link de uma notícia em texto limpo.

A extração é dividida em duas funções: `extrair_de_html` é pura e testável,
`extrair_noticia` acrescenta o download. Essa separação é o que permite testar
sem internet.

Como o app roda num servidor público e baixa qualquer link colado pelo
usuário, `extrair_noticia` só aceita URLs http/https que resolvem para IPs
públicos — inclusive em cada redirecionamento — para que ninguém use o
servidor como ponte para a rede interna (SSRF).
"""

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests
import trafilatura

from verdade_ou_fake.tipos import Noticia

TAMANHO_MINIMO = 100
TIMEOUT_SEGUNDOS = 15
MAX_REDIRECIONAMENTOS = 5
TAMANHO_MAXIMO_BYTES = 5 * 1024 * 1024
ESQUEMAS_PERMITIDOS = {"http", "https"}


class UrlNaoPermitida(ValueError):
    """A URL não pode ser baixada pelo servidor (esquema ou destino proibido)."""


def validar_url(url: str, resolver=socket.getaddrinfo) -> None:
    """Levanta `UrlNaoPermitida` se a URL não for http/https para um IP público.

    Todos os endereços para os quais o host resolve precisam ser globais:
    basta um apontar para loopback, rede privada ou link-local (onde ficam
    os endpoints de metadados da nuvem) para a URL ser recusada.
    """
    partes = urlparse(url)
    if partes.scheme not in ESQUEMAS_PERMITIDOS or not partes.hostname:
        raise UrlNaoPermitida("Só aceitamos links http:// ou https://.")

    try:
        enderecos = resolver(partes.hostname, partes.port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, ValueError) as erro:
        raise UrlNaoPermitida(f"Não foi possível resolver o endereço {partes.hostname}.") from erro

    for endereco in enderecos:
        ip = ipaddress.ip_address(endereco[4][0].split("%")[0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            raise UrlNaoPermitida("O link aponta para um endereço interno, que não pode ser acessado.")


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


def _baixar_limitado(resposta) -> str | None:
    """Lê o corpo até `TAMANHO_MAXIMO_BYTES`; devolve None se passar disso."""
    conteudo = bytearray()
    for bloco in resposta.iter_content(chunk_size=64 * 1024):
        conteudo.extend(bloco)
        if len(conteudo) > TAMANHO_MAXIMO_BYTES:
            return None
    try:
        return conteudo.decode(resposta.encoding or "utf-8", errors="replace")
    except LookupError:  # charset declarado pela página que o Python não conhece
        return conteudo.decode("utf-8", errors="replace")


def extrair_noticia(url: str) -> Noticia | None:
    """Baixa a página e extrai o conteúdo.

    Devolve None se a URL não for permitida, se o download falhar ou se a
    página for grande demais. Os redirecionamentos são seguidos manualmente
    para que cada destino passe de novo por `validar_url`.
    """
    atual = url
    try:
        for _ in range(MAX_REDIRECIONAMENTOS + 1):
            validar_url(atual)
            resposta = requests.get(
                atual,
                timeout=TIMEOUT_SEGUNDOS,
                headers={"User-Agent": "VerdadeOuFake/0.1 (projeto academico UnB)"},
                allow_redirects=False,
                stream=True,
            )
            try:
                if resposta.is_redirect:
                    atual = urljoin(atual, resposta.headers["Location"])
                    continue
                resposta.raise_for_status()
                html = _baixar_limitado(resposta)
            finally:
                resposta.close()
            if html is None:
                return None
            return extrair_de_html(html, atual)
    except (requests.RequestException, UrlNaoPermitida):
        return None

    return None

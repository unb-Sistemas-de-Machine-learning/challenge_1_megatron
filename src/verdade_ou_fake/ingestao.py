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
    pass


def validar_url(url: str, resolver=socket.getaddrinfo) -> None:
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
    conteudo = bytearray()
    for bloco in resposta.iter_content(chunk_size=64 * 1024):
        conteudo.extend(bloco)
        if len(conteudo) > TAMANHO_MAXIMO_BYTES:
            return None
    try:
        return conteudo.decode(resposta.encoding or "utf-8", errors="replace")
    except LookupError:
        return conteudo.decode("utf-8", errors="replace")


def extrair_noticia(url: str) -> Noticia | None:
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

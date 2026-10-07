import socket

import pytest
import requests

from verdade_ou_fake import ingestao
from verdade_ou_fake.ingestao import UrlNaoPermitida, extrair_noticia, validar_url

HTML_NOTICIA = (
    "<html><head><title>Matéria</title></head><body><article><p>"
    + "Texto longo da matéria sobre um medicamento e seus efeitos. " * 10
    + "</p></article></body></html>"
)


def _resolver_para(ip: str):
    def resolver(host, porta, *args, **kwargs):
        familia = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(familia, socket.SOCK_STREAM, 6, "", (ip, porta or 80))]

    return resolver


class _RespostaFalsa:
    def __init__(self, status=200, html="", location=None):
        self.status_code = status
        self.headers = {"Location": location} if location else {}
        self.encoding = "utf-8"
        self._corpo = html.encode("utf-8")

    @property
    def is_redirect(self):
        return self.status_code in (301, 302, 303, 307, 308) and "Location" in self.headers

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, chunk_size=1):
        for inicio in range(0, len(self._corpo), chunk_size):
            yield self._corpo[inicio : inicio + chunk_size]

    def close(self):
        pass


@pytest.mark.parametrize("url", ["ftp://exemplo.com/a", "file:///etc/passwd", "javascript:alert(1)", "exemplo.com"])
def test_rejeita_esquemas_que_nao_sao_http(url):
    with pytest.raises(UrlNaoPermitida):
        validar_url(url, resolver=_resolver_para("93.184.216.34"))


@pytest.mark.parametrize(
    "ip",
    ["127.0.0.1", "10.0.0.5", "172.16.3.4", "192.168.0.1", "169.254.169.254", "0.0.0.0", "::1", "fd00::1"],
)
def test_rejeita_hosts_que_resolvem_para_ip_interno(ip):
    with pytest.raises(UrlNaoPermitida):
        validar_url("http://interno.exemplo/", resolver=_resolver_para(ip))


def test_aceita_url_publica():
    validar_url("https://portal.exemplo.com/saude/materia", resolver=_resolver_para("93.184.216.34"))


def test_host_que_nao_resolve_e_rejeitado():
    def resolver_falha(*args, **kwargs):
        raise socket.gaierror("não resolve")

    with pytest.raises(UrlNaoPermitida):
        validar_url("https://nao-existe.exemplo/", resolver=resolver_falha)


def test_extrair_noticia_nao_baixa_url_interna(monkeypatch):
    monkeypatch.setattr(ingestao.socket, "getaddrinfo", _resolver_para("127.0.0.1"))
    chamadas = []
    monkeypatch.setattr(ingestao.requests, "get", lambda *a, **k: chamadas.append(a) or _RespostaFalsa())

    assert extrair_noticia("http://localhost:8501/") is None
    assert chamadas == []


def test_extrair_noticia_revalida_cada_redirecionamento(monkeypatch):
    def resolver(host, porta, *args, **kwargs):
        ip = "169.254.169.254" if host == "metadados.interno" else "93.184.216.34"
        return _resolver_para(ip)(host, porta)

    monkeypatch.setattr(ingestao.socket, "getaddrinfo", resolver)
    baixadas = []

    def get_falso(url, **kwargs):
        assert kwargs.get("allow_redirects") is False
        baixadas.append(url)
        return _RespostaFalsa(status=302, location="http://metadados.interno/latest/")

    monkeypatch.setattr(ingestao.requests, "get", get_falso)

    assert extrair_noticia("https://portal.exemplo.com/materia") is None
    assert baixadas == ["https://portal.exemplo.com/materia"]


def test_extrair_noticia_segue_redirecionamento_publico(monkeypatch):
    monkeypatch.setattr(ingestao.socket, "getaddrinfo", _resolver_para("93.184.216.34"))
    respostas = {
        "https://portal.exemplo.com/curto": _RespostaFalsa(status=301, location="/saude/materia"),
        "https://portal.exemplo.com/saude/materia": _RespostaFalsa(html=HTML_NOTICIA),
    }
    monkeypatch.setattr(ingestao.requests, "get", lambda url, **k: respostas[url])

    noticia = extrair_noticia("https://portal.exemplo.com/curto")

    assert noticia is not None
    assert noticia.url == "https://portal.exemplo.com/saude/materia"
    assert "medicamento" in noticia.texto


def test_extrair_noticia_desiste_apos_muitos_redirecionamentos(monkeypatch):
    monkeypatch.setattr(ingestao.socket, "getaddrinfo", _resolver_para("93.184.216.34"))
    monkeypatch.setattr(
        ingestao.requests,
        "get",
        lambda url, **k: _RespostaFalsa(status=302, location="https://portal.exemplo.com/loop"),
    )

    assert extrair_noticia("https://portal.exemplo.com/loop") is None


def test_extrair_noticia_corta_paginas_grandes_demais(monkeypatch):
    monkeypatch.setattr(ingestao.socket, "getaddrinfo", _resolver_para("93.184.216.34"))
    monkeypatch.setattr(ingestao, "TAMANHO_MAXIMO_BYTES", 50)
    monkeypatch.setattr(ingestao.requests, "get", lambda url, **k: _RespostaFalsa(html=HTML_NOTICIA))

    assert extrair_noticia("https://portal.exemplo.com/enorme") is None


def test_charset_desconhecido_cai_para_utf8(monkeypatch):
    monkeypatch.setattr(ingestao.socket, "getaddrinfo", _resolver_para("93.184.216.34"))
    resposta = _RespostaFalsa(html=HTML_NOTICIA)
    resposta.encoding = "charset-que-nao-existe"
    monkeypatch.setattr(ingestao.requests, "get", lambda url, **k: resposta)

    assert extrair_noticia("https://portal.exemplo.com/materia") is not None

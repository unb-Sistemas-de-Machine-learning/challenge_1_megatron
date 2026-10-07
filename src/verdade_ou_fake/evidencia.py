import os
import threading
import time
import xml.etree.ElementTree as ET

import requests

from verdade_ou_fake.tipos import Artigo

BASE_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TIMEOUT_SEGUNDOS = 12
MAX_ARTIGOS = 10
NOME_FERRAMENTA = "verdade_ou_fake"

INTERVALO_SEM_CHAVE = 1.1 / 3
INTERVALO_COM_CHAVE = 1.1 / 10

_trava_ritmo = threading.Lock()
_ultima_requisicao = 0.0

TIPOS_FORTES = {"Systematic Review", "Meta-Analysis"}
TIPOS_MODERADOS = {"Randomized Controlled Trial"}


def _texto_do_resumo(citacao: ET.Element) -> str:
    partes = [
        "".join(no.itertext()).strip()
        for no in citacao.iter("AbstractText")
    ]
    return " ".join(parte for parte in partes if parte)


def _ano_de_publicacao(citacao: ET.Element) -> int | None:
    for caminho in (".//DateCompleted/Year", ".//PubDate/Year", ".//ArticleDate/Year"):
        no_ano = citacao.find(caminho)
        if no_ano is not None and no_ano.text:
            try:
                return int(no_ano.text)
            except ValueError:
                continue
    return None


def parsear_artigos(xml: str) -> list[Artigo]:
    raiz = ET.fromstring(xml)
    artigos: list[Artigo] = []

    for citacao in raiz.iter("MedlineCitation"):
        no_pmid = citacao.find("PMID")
        no_titulo = citacao.find(".//ArticleTitle")
        tipos = [
            (no.text or "").strip()
            for no in citacao.iter("PublicationType")
            if no.text
        ]
        artigos.append(
            Artigo(
                pmid=no_pmid.text if no_pmid is not None and no_pmid.text else "",
                titulo="".join(no_titulo.itertext()).strip() if no_titulo is not None else "",
                resumo=_texto_do_resumo(citacao),
                tipos_estudo=tipos,
                ano=_ano_de_publicacao(citacao),
            )
        )

    return artigos


def _parametros_ncbi() -> dict:
    parametros = {"tool": NOME_FERRAMENTA}
    if chave := os.environ.get("NCBI_API_KEY"):
        parametros["api_key"] = chave
    if email := os.environ.get("NCBI_EMAIL"):
        parametros["email"] = email
    return parametros


def _intervalo_minimo() -> float:
    return INTERVALO_COM_CHAVE if os.environ.get("NCBI_API_KEY") else INTERVALO_SEM_CHAVE


def _aguardar_vez() -> None:
    global _ultima_requisicao
    with _trava_ritmo:
        espera = _ultima_requisicao + _intervalo_minimo() - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        _ultima_requisicao = time.monotonic()


FILTRO_ESTUDOS_FORTES = (
    "(systematic review[pt] OR meta-analysis[pt] OR randomized controlled trial[pt])"
    " NOT (animals[mh] NOT humans[mh])"
)


def buscar_pmids(termo: str, retmax: int = MAX_ARTIGOS) -> list[str]:
    _aguardar_vez()
    resposta = requests.get(
        f"{BASE_EUTILS}/esearch.fcgi",
        params={
            "db": "pubmed",
            "term": termo,
            "retmode": "json",
            "retmax": retmax,
            "sort": "relevance",
            **_parametros_ncbi(),
        },
        timeout=TIMEOUT_SEGUNDOS,
    )
    resposta.raise_for_status()
    return resposta.json()["esearchresult"]["idlist"]


def baixar_artigos(pmids: list[str]) -> list[Artigo]:
    if not pmids:
        return []
    _aguardar_vez()
    resposta = requests.post(
        f"{BASE_EUTILS}/efetch.fcgi",
        data={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", **_parametros_ncbi()},
        timeout=TIMEOUT_SEGUNDOS * 2,
    )
    resposta.raise_for_status()
    return parsear_artigos(resposta.text)


def buscar_artigos_ao_vivo(termo: str, retmax: int = 8) -> list[Artigo]:
    try:
        pmids = buscar_pmids(f"({termo}) AND {FILTRO_ESTUDOS_FORTES}", retmax)
        if not pmids:
            pmids = buscar_pmids(termo, retmax)
        return [a for a in baixar_artigos(pmids) if a.resumo]
    except (requests.RequestException, KeyError, ValueError, ET.ParseError):
        return []

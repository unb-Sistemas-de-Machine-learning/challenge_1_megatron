"""Etapa [2b] — busca literatura científica sobre a alegação no PubMed.

Usa a API E-utilities do NCBI, que é gratuita e não exige chave. O parsing do
XML fica em funções puras, testadas com uma resposta gravada; só
`buscar_evidencia` toca a rede.

Documentação da API: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""

import xml.etree.ElementTree as ET

import requests

from verdade_ou_fake.tipos import Alegacao, Artigo, Evidencia

BASE_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TIMEOUT_SEGUNDOS = 20
MAX_ARTIGOS = 10

# Tipos de estudo em ordem decrescente de força de evidência.
TIPOS_FORTES = {"Systematic Review", "Meta-Analysis"}
TIPOS_MODERADOS = {"Randomized Controlled Trial"}


def montar_query(alegacao: Alegacao) -> str:
    """Monta a query do PubMed a partir dos termos em inglês."""
    return f'"{alegacao.medicamento_en}"[MeSH Terms] AND "{alegacao.condicao_en}"[MeSH Terms]'


def _texto_do_resumo(citacao: ET.Element) -> str:
    """Junta as seções do resumo, que no PubMed vêm divididas em vários nós."""
    partes = [
        (no.text or "").strip()
        for no in citacao.iter("AbstractText")
    ]
    return " ".join(parte for parte in partes if parte)


def _ano_de_publicacao(citacao: ET.Element) -> int | None:
    no_ano = citacao.find(".//DateCompleted/Year")
    if no_ano is None or not no_ano.text:
        return None
    try:
        return int(no_ano.text)
    except ValueError:
        return None


def parsear_artigos(xml: str) -> list[Artigo]:
    """Converte a resposta XML do efetch em uma lista de Artigo."""
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
                titulo=no_titulo.text if no_titulo is not None and no_titulo.text else "",
                resumo=_texto_do_resumo(citacao),
                tipos_estudo=tipos,
                ano=_ano_de_publicacao(citacao),
            )
        )

    return artigos


def classificar_forca(artigos: list[Artigo]) -> str:
    """Devolve a força do melhor artigo encontrado.

    Segue a hierarquia de evidência: uma revisão sistemática vale mais que dez
    estudos isolados, então a força do conjunto é a do melhor item, não a média.
    """
    if not artigos:
        return "nenhuma"

    todos_os_tipos = {tipo for artigo in artigos for tipo in artigo.tipos_estudo}

    if todos_os_tipos & TIPOS_FORTES:
        return "forte"
    if todos_os_tipos & TIPOS_MODERADOS:
        return "moderada"
    return "fraca"


def montar_evidencia(artigos: list[Artigo]) -> Evidencia:
    """Empacota os artigos encontrados no formato que a fusão consome."""
    if not artigos:
        return Evidencia(cobertura="nao_cobre", forca="nenhuma", artigos=[])
    return Evidencia(
        cobertura="encontrada",
        forca=classificar_forca(artigos),
        artigos=artigos,
    )


def buscar_evidencia(alegacao: Alegacao) -> Evidencia:
    """Consulta o PubMed e devolve a evidência encontrada."""
    try:
        resposta_busca = requests.get(
            f"{BASE_EUTILS}/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": montar_query(alegacao),
                "retmode": "json",
                "retmax": MAX_ARTIGOS,
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        resposta_busca.raise_for_status()
        pmids = resposta_busca.json()["esearchresult"]["idlist"]

        if not pmids:
            return montar_evidencia([])

        resposta_artigos = requests.get(
            f"{BASE_EUTILS}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
            timeout=TIMEOUT_SEGUNDOS,
        )
        resposta_artigos.raise_for_status()
    except (requests.RequestException, KeyError, ValueError):
        return montar_evidencia([])

    return montar_evidencia(parsear_artigos(resposta_artigos.text))
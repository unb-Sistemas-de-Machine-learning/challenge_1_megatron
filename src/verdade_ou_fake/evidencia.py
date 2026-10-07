"""Etapa [2b] — busca literatura científica sobre a alegação no PubMed.

Usa a API E-utilities do NCBI, que é gratuita e não exige chave. O parsing do
XML fica em funções puras, testadas com uma resposta gravada; só
`buscar_evidencia` toca a rede.

Em produção, configure `NCBI_API_KEY` (gratuita, sobe o limite de 3 para 10
requisições/s por IP) e `NCBI_EMAIL` (contato pedido pelo NCBI). As
requisições deste processo são espaçadas para respeitar esse limite mesmo
com vários usuários simultâneos.

Documentação da API: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""

import os
import threading
import time
import xml.etree.ElementTree as ET

import requests

from verdade_ou_fake.tipos import Alegacao, Artigo, Evidencia

BASE_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TIMEOUT_SEGUNDOS = 20
MAX_ARTIGOS = 10
NOME_FERRAMENTA = "verdade_ou_fake"

# Limites documentados pelo NCBI, com folga de 10%.
INTERVALO_SEM_CHAVE = 1.1 / 3
INTERVALO_COM_CHAVE = 1.1 / 10

_trava_ritmo = threading.Lock()
_ultima_requisicao = 0.0

# Tipos de estudo em ordem decrescente de força de evidência.
TIPOS_FORTES = {"Systematic Review", "Meta-Analysis"}
TIPOS_MODERADOS = {"Randomized Controlled Trial"}


def montar_query(alegacao: Alegacao) -> str:
    """Monta a query do PubMed a partir dos termos em inglês."""
    return f'"{alegacao.medicamento_en}"[MeSH Terms] AND "{alegacao.condicao_en}"[MeSH Terms]'


def _texto_do_resumo(citacao: ET.Element) -> str:
    """Junta as seções do resumo, que no PubMed vêm divididas em vários nós."""
    # itertext() porque resumos trazem marcação interna (<i>, <sup>) que
    # faria `.text` cortar a frase no primeiro elemento filho.
    partes = [
        "".join(no.itertext()).strip()
        for no in citacao.iter("AbstractText")
    ]
    return " ".join(parte for parte in partes if parte)


def _ano_de_publicacao(citacao: ET.Element) -> int | None:
    # DateCompleted falta em artigos recentes; a data do periódico cobre o resto.
    for caminho in (".//DateCompleted/Year", ".//PubDate/Year", ".//ArticleDate/Year"):
        no_ano = citacao.find(caminho)
        if no_ano is not None and no_ano.text:
            try:
                return int(no_ano.text)
            except ValueError:
                continue
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
                titulo="".join(no_titulo.itertext()).strip() if no_titulo is not None else "",
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


def _parametros_ncbi() -> dict:
    """Identificação pedida pelo NCBI; chave e e-mail vêm do ambiente."""
    parametros = {"tool": NOME_FERRAMENTA}
    if chave := os.environ.get("NCBI_API_KEY"):
        parametros["api_key"] = chave
    if email := os.environ.get("NCBI_EMAIL"):
        parametros["email"] = email
    return parametros


def _intervalo_minimo() -> float:
    return INTERVALO_COM_CHAVE if os.environ.get("NCBI_API_KEY") else INTERVALO_SEM_CHAVE


def _aguardar_vez() -> None:
    """Espaça as requisições ao NCBI feitas por todas as sessões do processo."""
    global _ultima_requisicao
    with _trava_ritmo:
        espera = _ultima_requisicao + _intervalo_minimo() - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        _ultima_requisicao = time.monotonic()


FILTRO_ESTUDOS_FORTES = (
    "(systematic review[pt] OR meta-analysis[pt] OR randomized controlled trial[pt])"
    # Filtro padrão para excluir estudos só em animais sem perder artigos
    # recentes, que ainda não receberam indexação MeSH.
    " NOT (animals[mh] NOT humans[mh])"
)


def buscar_pmids(termo: str, retmax: int = MAX_ARTIGOS) -> list[str]:
    """Roda o esearch e devolve os PMIDs, ordenados por relevância."""
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
    """Roda o efetch para uma lista de PMIDs (use lotes de até ~150)."""
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
    """Busca ampliada usada pelo RAG quando a base local não cobre a alegação.

    Tenta primeiro só estudos fortes (revisões, meta-análises, ensaios
    randomizados); se não houver nenhum, aceita qualquer tipo. Nunca levanta:
    falha de rede vira lista vazia, e o RAG responde com o que já tinha.
    """
    try:
        pmids = buscar_pmids(f"({termo}) AND {FILTRO_ESTUDOS_FORTES}", retmax)
        if not pmids:
            pmids = buscar_pmids(termo, retmax)
        return [a for a in baixar_artigos(pmids) if a.resumo]
    except (requests.RequestException, KeyError, ValueError, ET.ParseError):
        return []


def buscar_evidencia(alegacao: Alegacao) -> Evidencia:
    """Consulta o PubMed e devolve a evidência encontrada."""
    try:
        _aguardar_vez()
        resposta_busca = requests.get(
            f"{BASE_EUTILS}/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": montar_query(alegacao),
                "retmode": "json",
                "retmax": MAX_ARTIGOS,
                **_parametros_ncbi(),
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        resposta_busca.raise_for_status()
        pmids = resposta_busca.json()["esearchresult"]["idlist"]

        if not pmids:
            return montar_evidencia([])

        _aguardar_vez()
        resposta_artigos = requests.get(
            f"{BASE_EUTILS}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", **_parametros_ncbi()},
            timeout=TIMEOUT_SEGUNDOS,
        )
        resposta_artigos.raise_for_status()
    except (requests.RequestException, KeyError, ValueError):
        return montar_evidencia([])

    return montar_evidencia(parsear_artigos(resposta_artigos.text))
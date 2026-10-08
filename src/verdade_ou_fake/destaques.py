import asyncio
import csv
import io
import json
import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

import requests

from verdade_ou_fake import rag
from verdade_ou_fake.base import documento_de_artigo, indexar
from verdade_ou_fake.llm import LLMIndisponivel

URL_BUSCA = "https://news.google.com/rss/search"
URL_SAUDE = "https://news.google.com/rss/headlines/section/topic/HEALTH"
IDIOMA = {"hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"}
AGENTE = {"User-Agent": "VerdadeOuFake/1.0 (projeto academico UnB)"}
TIMEOUT_SEGUNDOS = 12
COLUNAS_DE_TEMA = ("alegacao", "alegação", "tema", "titulo", "título")
COLUNAS_DE_DATA = ("data", "semana", "dia")
FORMATOS_DE_DATA = ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y")
DIAS_DE_VALIDADE = 7
NOTICIAS_POR_TEMA = 3
MANCHETES_LIDAS = 40
ORIGEM_PLANILHA = "curadoria"
ORIGEM_NOTICIAS = "google_noticias"

PROMPT_MANCHETES = """Você recebe manchetes de saúde do dia. Escolha apenas as que \
afirmam que uma intervenção específica e nomeada (um medicamento, vacina, suplemento, \
alimento, exercício ou terapia identificada pelo nome) previne, trata, cura ou causa uma \
doença específica. Descarte manchetes genéricas ("novo tratamento", "novos medicamentos"), \
de política de saúde, oferta de serviços, campanhas, eventos, gestão e estatísticas. \
Reescreva cada escolhida como uma alegação curta e afirmativa em português, com o nome da \
intervenção e o da doença, sem citar veículo, cidade ou instituição. Responda apenas com um \
objeto JSON: {"alegacoes": ["...", "..."]}, com no máximo %d itens e sem repetir assunto. \
Se nenhuma manchete servir, responda {"alegacoes": []}."""

registro = logging.getLogger(__name__)


def _baixar(url: str, parametros: dict | None = None) -> str:
    resposta = requests.get(url, params=parametros, headers=AGENTE, timeout=TIMEOUT_SEGUNDOS)
    resposta.raise_for_status()
    resposta.encoding = "utf-8"
    return resposta.text


def _data_da_linha(linha: dict) -> date | None:
    for coluna in COLUNAS_DE_DATA:
        valor = (linha.get(coluna) or "").strip()
        for formato in FORMATOS_DE_DATA:
            try:
                return datetime.strptime(valor, formato).date()
            except ValueError:
                continue
    return None


def parsear_planilha(texto_csv: str, hoje: date | None = None) -> list[str]:
    hoje = hoje or date.today()
    leitor = csv.DictReader(io.StringIO(texto_csv))
    if not leitor.fieldnames:
        return []
    leitor.fieldnames = [nome.strip().lower() for nome in leitor.fieldnames]
    coluna = next((c for c in COLUNAS_DE_TEMA if c in leitor.fieldnames), leitor.fieldnames[0])
    temas: list[str] = []
    for linha in leitor:
        tema = " ".join((linha.get(coluna) or "").split())
        quando = _data_da_linha(linha)
        vencido = quando is not None and not (
            hoje - timedelta(days=DIAS_DE_VALIDADE) <= quando <= hoje + timedelta(days=1)
        )
        if len(tema) >= 8 and not vencido and tema not in temas:
            temas.append(tema[:300])
    return temas


def parsear_rss(xml: str, limite: int) -> list[dict]:
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError:
        return []
    noticias = []
    for item in raiz.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        fonte = (item.findtext("source") or "").strip()
        if fonte and titulo.endswith(f" - {fonte}"):
            titulo = titulo[: -len(fonte) - 3]
        if titulo and url.startswith("https://"):
            noticias.append({"titulo": titulo, "url": url, "fonte": fonte})
        if len(noticias) >= limite:
            break
    return noticias


def ler_planilha(url: str, baixar=_baixar) -> list[str]:
    try:
        return parsear_planilha(baixar(url))
    except (requests.RequestException, csv.Error) as erro:
        registro.warning("Planilha de destaques indisponível: %s", erro)
        return []


def noticias_sobre(tema: str, baixar=_baixar) -> list[dict]:
    try:
        xml = baixar(URL_BUSCA, {"q": f"{tema} when:7d", **IDIOMA})
    except requests.RequestException:
        return []
    return parsear_rss(xml, NOTICIAS_POR_TEMA)


def manchetes_de_saude(baixar=_baixar) -> list[str]:
    try:
        xml = baixar(URL_SAUDE, IDIOMA)
    except requests.RequestException:
        return []
    return [noticia["titulo"] for noticia in parsear_rss(xml, MANCHETES_LIDAS)]


async def alegacoes_das_manchetes(servico: rag.Servico, manchetes: list[str], limite: int) -> list[str]:
    if servico.llm is None or not manchetes or limite <= 0:
        return []
    try:
        bruto = await servico.llm.completar(
            [
                {"role": "system", "content": PROMPT_MANCHETES % limite},
                {"role": "user", "content": "\n".join(f"- {m}" for m in manchetes)},
            ],
            max_tokens=700,
            formato_json=True,
        )
        itens = json.loads(bruto[bruto.index("{") : bruto.rindex("}") + 1]).get("alegacoes", [])
    except (LLMIndisponivel, ValueError, AttributeError):
        return []
    return [" ".join(str(i).split())[:300] for i in itens if len(str(i).strip()) >= 8][:limite]


async def _preparar_tema(servico: rag.Servico, tema: str, origem: str, buscar_noticias) -> dict | None:
    alegacao = await rag.entender_alegacao(servico, tema)
    if not alegacao.saude:
        return None
    novos = 0
    if alegacao.pubmed and servico.config.busca_ao_vivo:
        artigos = await asyncio.to_thread(servico.buscar_ao_vivo, alegacao.pubmed)
        novos = await asyncio.to_thread(
            indexar,
            servico.banco,
            servico.embutir,
            [documento_de_artigo(a) for a in artigos],
            "destaque",
        )
    veredito: dict = {}
    async for evento in rag.analisar(servico, tema, tipo_entrada="destaque"):
        if evento["tipo"] == "veredito":
            veredito = evento
    if not veredito:
        return None
    if origem == ORIGEM_NOTICIAS and not (
        veredito["codigo"] in rag.VEREDITOS_AFIRMATIVOS and veredito["confianca"] == "alta"
    ):
        return None
    return {
        "tema": tema,
        "alegacao": alegacao.texto,
        "origem": origem,
        "veredito": veredito["codigo"],
        "confianca": veredito["confianca"],
        "resumo": veredito["resumo"],
        "noticias": await asyncio.to_thread(buscar_noticias, alegacao.texto),
        "novos_artigos": novos,
    }


async def atualizar(
    servico: rag.Servico,
    ler=ler_planilha,
    manchetes=manchetes_de_saude,
    buscar_noticias=noticias_sobre,
    pausa: float | None = None,
) -> int:
    config = servico.config
    pausa = config.destaques_pausa if pausa is None else pausa
    temas: list[tuple[str, str]] = []
    if config.planilha_csv:
        temas += [(t, ORIGEM_PLANILHA) for t in await asyncio.to_thread(ler, config.planilha_csv)]
    temas = temas[: config.destaques_maximo]
    if config.destaques_automaticos and len(temas) < config.destaques_maximo:
        lidas = await asyncio.to_thread(manchetes)
        extras = await alegacoes_das_manchetes(servico, lidas, config.destaques_maximo)
        temas += [(t, ORIGEM_NOTICIAS) for t in extras if t not in {tema for tema, _ in temas}]

    prontos = []
    for indice, (tema, origem) in enumerate(temas):
        if indice and pausa:
            await asyncio.sleep(pausa)
        try:
            item = await _preparar_tema(servico, tema, origem, buscar_noticias)
        except Exception:
            registro.exception("Falha ao preparar o destaque %r", tema)
            continue
        if item is not None:
            prontos.append(item)
    if prontos:
        servico.banco.substituir_destaques(prontos)
    registro.info("Destaques atualizados: %d de %d temas", len(prontos), len(temas))
    return len(prontos)

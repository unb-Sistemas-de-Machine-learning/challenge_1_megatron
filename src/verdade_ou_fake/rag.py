import asyncio
import hashlib
import json
import re
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

from verdade_ou_fake.banco import Banco
from verdade_ou_fake.base import documento_de_artigo, indexar
from verdade_ou_fake.config import Config
from verdade_ou_fake.embeddings import Embutidor
from verdade_ou_fake.evidencia import TIPOS_FORTES, TIPOS_MODERADOS, buscar_artigos_ao_vivo
from verdade_ou_fake.ingestao import extrair_noticia
from verdade_ou_fake.llm import ClienteLLM, LLMIndisponivel
from verdade_ou_fake.recuperacao import Recuperador, Trecho
from verdade_ou_fake.vocabulario import extrair_alegacao

ROTULOS = {
    "APOIADA": "Tem respaldo científico",
    "CONTESTADA": "A ciência contradiz",
    "EXAGERADA": "Há base, mas a alegação exagera",
    "INCONCLUSIVA": "Evidência insuficiente ou conflitante",
    "NAO_VERIFICAVEL": "Não foi possível verificar",
    "FORA_DO_ESCOPO": "Fora do escopo",
}
VEREDITOS_AFIRMATIVOS = {"APOIADA", "CONTESTADA", "EXAGERADA"}
ORDEM_CONFIANCA = ["baixa", "media", "alta"]
PADRAO_URL = re.compile(r"^https?://\S+$")
PADRAO_CITACAO = re.compile(r"\[(\d+(?:\s*[,;e]\s*\d+)*)\]")
SEPARADOR = "---"
TAMANHO_MINIMO = 12
FOLGA_SIMILARIDADE = 0.12
CANDIDATOS = 15

PROMPT_ALEGACAO = """Você extrai a alegação central de saúde de um texto em português.
Responda apenas com um objeto JSON com as chaves:
- "saude": true se o texto afirma algo sobre os efeitos, benefícios ou riscos de um \
medicamento, tratamento, suplemento, vacina, terapia, alimento ou prática sobre a saúde \
(tratar, prevenir, curar ou causar uma doença); false se o assunto não é saúde.
- "alegacao": a alegação principal em uma frase curta e afirmativa em português \
(ex.: "Ivermectina cura covid-19").
- "consulta_en": a mesma alegação em inglês científico \
(ex.: "ivermectin for the treatment of COVID-19").
- "pubmed": consulta para o PubMed em inglês com exatamente 2 conceitos, a intervenção e a \
condição, cada um com uma ou duas palavras, unidos por AND (ex.: "ivermectin AND covid-19")."""

PROMPT_VEREDITO = """Você é um checador de fatos de saúde. Avalie a ALEGAÇÃO usando \
exclusivamente as FONTES numeradas, que são resumos de estudos científicos.

Regras:
- Toda frase factual termina com a citação da fonte no formato [n]. Cite só números da lista.
- Não use conhecimento que não esteja nas fontes. Não invente estudos, números ou datas.
- Revisões sistemáticas e meta-análises pesam mais que estudos isolados; estudos recentes \
pesam mais que antigos.
- Se as fontes não tratam da alegação ou se contradizem entre si, o veredito é INCONCLUSIVA. \
Falta de estudo não prova que algo é falso.
- Escreva em português do Brasil para um público leigo, sem jargão. Não dê orientação \
médica individual.

Vereditos possíveis:
- APOIADA: as fontes sustentam a alegação como foi formulada.
- CONTESTADA: as fontes mostram que não funciona ou contradizem a alegação.
- EXAGERADA: existe algum efeito ou base, mas a alegação vai além do que os estudos mostram.
- INCONCLUSIVA: evidência insuficiente, indireta ou conflitante.

Responda exatamente neste formato:
VEREDITO: <APOIADA|CONTESTADA|EXAGERADA|INCONCLUSIVA>
CONFIANCA: <alta|media|baixa>
RESUMO: <uma frase de até 25 palavras, sem citação>
---
<dois ou três parágrafos curtos, no máximo 130 palavras no total, com citações [n]>"""


@dataclass
class Servico:
    config: Config
    banco: Banco
    recuperador: Recuperador
    embutir: Embutidor
    vocabulario: dict
    llm: ClienteLLM | None = None
    calcular_estilo: Callable[[str], float] | None = None
    versao_base: str = ""
    extrair_noticia: Callable = extrair_noticia
    buscar_ao_vivo: Callable = buscar_artigos_ao_vivo


@dataclass
class Alegacao:
    texto: str
    consulta: str
    termos: str
    pubmed: str | None
    saude: bool = True


@dataclass
class Resultado:
    codigo: str = "INCONCLUSIVA"
    confianca: str = "baixa"
    resumo: str = ""
    corpo: str = ""
    citadas: list[int] = field(default_factory=list)
    aviso: str | None = None


class FiltroDeCitacoes:
    def __init__(self, total_fontes: int):
        self._total = total_fontes
        self._pendente = ""
        self.citadas: set[int] = set()

    def _substituir(self, casamento: re.Match) -> str:
        numeros = [int(n) for n in re.findall(r"\d+", casamento.group(1))]
        validos = [n for n in numeros if 1 <= n <= self._total]
        self.citadas.update(validos)
        return "".join(f"[{n}]" for n in validos)

    def alimentar(self, pedaco: str) -> str:
        texto = self._pendente + pedaco
        abertura = texto.rfind("[")
        if abertura != -1 and "]" not in texto[abertura:] and len(texto) - abertura < 16:
            self._pendente = texto[abertura:]
            texto = texto[:abertura]
        else:
            self._pendente = ""
        return PADRAO_CITACAO.sub(self._substituir, texto)

    def encerrar(self) -> str:
        resto, self._pendente = self._pendente, ""
        return PADRAO_CITACAO.sub(self._substituir, resto)


def forca_da_fonte(tipos: list[str]) -> str:
    if set(tipos) & TIPOS_FORTES:
        return "forte"
    if set(tipos) & TIPOS_MODERADOS:
        return "moderada"
    return "fraca"


def chave_de_cache(texto: str, versao_base: str) -> str:
    normalizado = " ".join(texto.lower().split())
    return hashlib.sha256(f"{versao_base}|{normalizado}".encode()).hexdigest()


def interpretar_cabecalho(cabecalho: str) -> Resultado:
    def campo(nome: str) -> str:
        casamento = re.search(rf"{nome}\s*:\s*(.+)", cabecalho, re.IGNORECASE)
        return casamento.group(1).strip().strip("*<>") if casamento else ""

    codigo = re.sub(r"[^A-Z_]", "", campo("VEREDITO").upper())
    confianca = campo("CONFIAN[CÇ]A").lower().replace("é", "e")
    return Resultado(
        codigo=codigo if codigo in VEREDITOS_AFIRMATIVOS | {"INCONCLUSIVA"} else "INCONCLUSIVA",
        confianca=confianca if confianca in ORDEM_CONFIANCA else "baixa",
        resumo=campo("RESUMO"),
    )


def aplicar_guardas(resultado: Resultado, fontes: list[dict]) -> bool:
    antes = (resultado.codigo, resultado.confianca)
    if resultado.codigo in VEREDITOS_AFIRMATIVOS and not resultado.citadas:
        resultado.codigo = "INCONCLUSIVA"
        resultado.confianca = "baixa"
        resultado.aviso = "A resposta não citou nenhuma fonte, então o veredito foi rebaixado."
    else:
        forcas = {fontes[n - 1]["forca"] for n in resultado.citadas}
        teto = "alta" if "forte" in forcas else "media" if "moderada" in forcas else "baixa"
        if ORDEM_CONFIANCA.index(resultado.confianca) > ORDEM_CONFIANCA.index(teto):
            resultado.confianca = teto
            resultado.aviso = (
                "Confiança limitada pelo tipo de estudo citado: "
                "não há revisão sistemática ou meta-análise entre as fontes usadas."
            )
    return antes != (resultado.codigo, resultado.confianca)


def evento_veredito(resultado: Resultado) -> dict:
    return {
        "tipo": "veredito",
        "codigo": resultado.codigo,
        "rotulo": ROTULOS[resultado.codigo],
        "confianca": resultado.confianca,
        "resumo": resultado.resumo,
    }


def _alegacao_pelo_vocabulario(texto: str, vocabulario: dict) -> Alegacao:
    par = extrair_alegacao(texto, vocabulario)
    if par is None:
        resumo = " ".join(texto.split())[:240]
        return Alegacao(texto=resumo, consulta=texto[:1000], termos=texto[:300], pubmed=None)
    return Alegacao(
        texto=f"{par.medicamento_pt.capitalize()} trata {par.condicao_pt}",
        consulta=f"{par.medicamento_en} for the treatment of {par.condicao_en}",
        termos=f"{par.medicamento_en} {par.condicao_en}",
        pubmed=f"{par.medicamento_en} AND {par.condicao_en}",
    )


async def entender_alegacao(servico: Servico, texto: str) -> Alegacao:
    reserva = _alegacao_pelo_vocabulario(texto, servico.vocabulario)
    if servico.llm is None:
        return reserva
    try:
        bruto = await servico.llm.completar(
            [
                {"role": "system", "content": PROMPT_ALEGACAO},
                {"role": "user", "content": texto[:3000]},
            ],
            modelo=servico.config.llm_modelo_rapido,
            max_tokens=200,
            formato_json=True,
        )
        dados = json.loads(bruto[bruto.index("{") : bruto.rindex("}") + 1])
        alegacao = str(dados.get("alegacao") or "").strip()
        consulta = str(dados.get("consulta_en") or "").strip()
        if not alegacao or not consulta:
            return reserva
        pubmed = str(dados.get("pubmed") or "").strip() or reserva.pubmed
        return Alegacao(
            texto=alegacao,
            consulta=f"{consulta}. {alegacao}",
            termos=f"{consulta} {pubmed or ''}".replace(" AND ", " "),
            pubmed=pubmed,
            saude=bool(dados.get("saude", True)),
        )
    except (LLMIndisponivel, ValueError, TypeError):
        return reserva


def _conceitos(pubmed: str | None) -> list[list[str]]:
    if not pubmed:
        return []
    conceitos = []
    for parte in re.split(r"\s+AND\s+", pubmed, flags=re.IGNORECASE):
        palavras = [p for p in re.findall(r"[\w-]+", parte.lower()) if len(p) >= 4 and p != "or"]
        if palavras:
            conceitos.append(palavras)
    return conceitos


def _cobre(trecho: Trecho, conceitos: list[list[str]]) -> bool:
    texto = f"{trecho.documento.titulo} {trecho.documento.texto}".lower()
    return all(any(palavra in texto for palavra in conceito) for conceito in conceitos)


def selecionar(trechos: list[Trecho], pubmed: str | None, minimo: float, k: int) -> list[Trecho]:
    conceitos = _conceitos(pubmed)
    if conceitos:
        completos = [t for t in trechos if _cobre(t, conceitos) and t.similaridade >= minimo - FOLGA_SIMILARIDADE]
        if completos:
            return completos[:k]
    return [t for t in trechos if t.similaridade >= minimo + FOLGA_SIMILARIDADE][:k]


def _fontes(trechos: list[Trecho]) -> list[dict]:
    return [
        {
            "n": n,
            "titulo": t.documento.titulo,
            "url": t.documento.url,
            "ano": t.documento.ano,
            "tipos": t.documento.tipos,
            "forca": forca_da_fonte(t.documento.tipos),
            "origem": "PubMed",
        }
        for n, t in enumerate(trechos, 1)
    ]


def _mensagens_do_veredito(alegacao: Alegacao, texto: str, trechos: list[Trecho]) -> list[dict]:
    blocos = []
    for n, t in enumerate(trechos, 1):
        tipos = ", ".join(t.documento.tipos[:3]) or "tipo não informado"
        blocos.append(
            f"[{n}] {t.documento.titulo} ({tipos}; {t.documento.ano or 's/d'})\n"
            f"{t.documento.texto[:1100]}"
        )
    usuario = f"ALEGAÇÃO: {alegacao.texto}\n\n"
    if len(texto) > len(alegacao.texto) + 40:
        usuario += f"TRECHO DO TEXTO ORIGINAL: {texto[:1000]}\n\n"
    usuario += "FONTES:\n" + "\n\n".join(blocos)
    return [{"role": "system", "content": PROMPT_VEREDITO}, {"role": "user", "content": usuario}]


async def _redigir(
    servico: Servico, mensagens: list[dict], fontes: list[dict], resultado: Resultado
) -> AsyncIterator[dict]:
    filtro = FiltroDeCitacoes(len(fontes))
    cabecalho = ""
    no_corpo = False
    async for pedaco in servico.llm.transmitir(mensagens):
        if not no_corpo:
            cabecalho += pedaco
            if SEPARADOR not in cabecalho and len(cabecalho) < 700:
                continue
            antes, _, pedaco = cabecalho.partition(SEPARADOR)
            interpretado = interpretar_cabecalho(antes)
            resultado.codigo = interpretado.codigo
            resultado.confianca = interpretado.confianca
            resultado.resumo = interpretado.resumo
            yield evento_veredito(resultado)
            no_corpo = True
            pedaco = pedaco.lstrip("-\n ")
        limpo = filtro.alimentar(pedaco)
        if limpo:
            resultado.corpo += limpo
            yield {"tipo": "texto", "texto": limpo}
    if not no_corpo:
        interpretado = interpretar_cabecalho(cabecalho)
        resultado.codigo, resultado.confianca = interpretado.codigo, interpretado.confianca
        resultado.resumo = interpretado.resumo
        yield evento_veredito(resultado)
    resto = filtro.encerrar()
    if resto:
        resultado.corpo += resto
        yield {"tipo": "texto", "texto": resto}
    resultado.citadas = sorted(filtro.citadas)


def _sem_fontes(alegacao: Alegacao) -> Resultado:
    return Resultado(
        codigo="NAO_VERIFICAVEL",
        confianca="baixa",
        resumo="Não encontramos estudos científicos sobre essa alegação na nossa base nem no PubMed.",
        corpo=(
            "Isso **não significa que a alegação seja falsa**: ausência de estudo não é prova "
            "de ineficácia. Significa só que não há literatura suficiente para checar. "
            "Na dúvida, converse com um profissional de saúde antes de agir."
        ),
    )


def _sem_llm(fontes: list[dict]) -> Resultado:
    return Resultado(
        codigo="INCONCLUSIVA",
        confianca="baixa",
        resumo="Encontramos estudos relacionados, mas o redator automático está indisponível.",
        corpo=(
            "O serviço de linguagem que redige a análise não respondeu agora. "
            "As fontes abaixo são os estudos mais próximos da alegação; "
            "consulte os resumos originais pelos links."
        ),
        aviso="Modo degradado: veredito automático indisponível.",
    )


async def analisar(servico: Servico, entrada: str) -> AsyncIterator[dict]:
    inicio = time.monotonic()
    entrada = entrada.strip()
    eh_link = bool(PADRAO_URL.match(entrada))
    texto = entrada
    titulo_noticia = None

    if eh_link:
        yield {"tipo": "etapa", "texto": "Lendo a notícia"}
        pagina = servico.banco.obter_pagina(entrada)
        if pagina is None:
            noticia = await asyncio.to_thread(servico.extrair_noticia, entrada)
            if noticia is None:
                yield {
                    "tipo": "erro",
                    "mensagem": "Não conseguimos ler essa página. Ela pode exigir login, estar "
                    "atrás de paywall ou bloquear leitura automática. Cole o texto da notícia.",
                }
                return
            pagina = (noticia.titulo, noticia.texto)
            servico.banco.guardar_pagina(entrada, *pagina)
        titulo_noticia = pagina[0]
        texto = f"{pagina[0]}\n\n{pagina[1]}"

    if len(texto) < TAMANHO_MINIMO:
        yield {"tipo": "erro", "mensagem": "Escreva a alegação com um pouco mais de detalhe."}
        return

    chave = chave_de_cache(texto, servico.versao_base)
    guardados = servico.banco.buscar_cache(chave, servico.config.cache_horas * 3600)
    if guardados is not None:
        fim = {}
        for evento in guardados:
            if evento["tipo"] == "fim":
                fim = evento
                continue
            yield evento
        veredito = next((e for e in reversed(guardados) if e["tipo"] == "veredito"), {})
        consulta_id = servico.banco.registrar_consulta(
            chave=chave,
            tipo_entrada="link" if eh_link else "texto",
            veredito=veredito.get("codigo"),
            confianca=veredito.get("confianca"),
            do_cache=1,
            latencia_ms=int((time.monotonic() - inicio) * 1000),
        )
        yield {
            **fim,
            "tipo": "fim",
            "consulta_id": consulta_id,
            "latencia_ms": int((time.monotonic() - inicio) * 1000),
            "do_cache": True,
        }
        return

    emitidos: list[dict] = []

    def guardar(evento: dict) -> dict:
        emitidos.append(evento)
        return evento

    yield {"tipo": "etapa", "texto": "Identificando a alegação"}
    tarefa_estilo = (
        asyncio.create_task(asyncio.to_thread(servico.calcular_estilo, texto))
        if servico.calcular_estilo
        else None
    )
    alegacao = await entender_alegacao(servico, texto)
    yield guardar({"tipo": "alegacao", "texto": alegacao.texto, "titulo_noticia": titulo_noticia})

    resultado = Resultado()
    fontes: list[dict] = []
    foi_ao_vivo = False

    if not alegacao.saude:
        resultado = Resultado(
            codigo="FORA_DO_ESCOPO",
            confianca="alta",
            resumo="Este texto não parece fazer uma alegação sobre medicamento ou tratamento.",
            corpo=(
                "O sistema só checa alegações sobre **medicamentos, tratamentos, suplementos e "
                "terapias**. Tente colar o trecho que afirma que algo trata, previne ou cura "
                "uma doença."
            ),
        )
    else:
        yield {"tipo": "etapa", "texto": "Buscando estudos na base científica"}
        minimo = servico.config.similaridade_minima
        k = servico.config.fontes_por_resposta
        candidatos = await asyncio.to_thread(
            servico.recuperador.buscar, alegacao.consulta, alegacao.termos, CANDIDATOS
        )
        trechos = selecionar(candidatos, alegacao.pubmed, minimo, k)
        if len(trechos) < 2 and alegacao.pubmed and servico.config.busca_ao_vivo:
            yield {"tipo": "etapa", "texto": "Ampliando a busca no PubMed"}
            artigos = await asyncio.to_thread(servico.buscar_ao_vivo, alegacao.pubmed)
            if artigos:
                foi_ao_vivo = True
                await asyncio.to_thread(
                    indexar,
                    servico.banco,
                    servico.embutir,
                    [documento_de_artigo(a) for a in artigos],
                    "ao_vivo",
                )
                candidatos = await asyncio.to_thread(
                    servico.recuperador.buscar, alegacao.consulta, alegacao.termos, CANDIDATOS
                )
                trechos = selecionar(candidatos, alegacao.pubmed, minimo, k)
        fontes = _fontes(trechos)

        if tarefa_estilo is not None:
            try:
                risco = await asyncio.wait_for(tarefa_estilo, timeout=4)
                yield guardar({"tipo": "estilo", "risco": round(float(risco), 3)})
            except Exception:
                pass
            tarefa_estilo = None

        yield guardar({"tipo": "fontes", "fontes": fontes})

        if not fontes:
            resultado = _sem_fontes(alegacao)
        elif servico.llm is None:
            resultado = _sem_llm(fontes)
        else:
            yield {"tipo": "etapa", "texto": "Redigindo a análise"}
            try:
                async for evento in _redigir(
                    servico, _mensagens_do_veredito(alegacao, texto, trechos), fontes, resultado
                ):
                    yield guardar(evento)
                if aplicar_guardas(resultado, fontes):
                    yield guardar(evento_veredito(resultado))
            except LLMIndisponivel:
                resultado = _sem_llm(fontes)

    if tarefa_estilo is not None:
        tarefa_estilo.cancel()

    if not any(e["tipo"] == "veredito" for e in emitidos):
        yield guardar(evento_veredito(resultado))
        yield guardar({"tipo": "texto", "texto": resultado.corpo})

    latencia = int((time.monotonic() - inicio) * 1000)
    modelo = servico.llm.ultimo_modelo if servico.llm and resultado.citadas else None
    fim = {
        "tipo": "fim",
        "latencia_ms": latencia,
        "modelo": modelo,
        "do_cache": False,
        "citadas": resultado.citadas,
        "aviso": resultado.aviso,
    }
    degradado = resultado.aviso is not None and resultado.aviso.startswith("Modo degradado")
    consulta_id = servico.banco.registrar_consulta(
        chave=chave,
        tipo_entrada="link" if eh_link else "texto",
        alegacao=alegacao.texto,
        veredito=resultado.codigo,
        confianca=resultado.confianca,
        fontes=[f["url"] for f in fontes],
        citacoes_validas=len(resultado.citadas),
        busca_ao_vivo=int(foi_ao_vivo),
        modelo=modelo,
        latencia_ms=latencia,
        eventos=None if degradado else emitidos + [fim],
    )
    yield {**fim, "consulta_id": consulta_id}

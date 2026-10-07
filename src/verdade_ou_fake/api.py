import asyncio
import json
import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from verdade_ou_fake import rag, sinal_estilo
from verdade_ou_fake.banco import Banco
from verdade_ou_fake.base import construir, ler_manifesto
from verdade_ou_fake.config import Config, carregar_env
from verdade_ou_fake.embeddings import criar_embutidor
from verdade_ou_fake.llm import ClienteLLM
from verdade_ou_fake.recuperacao import Recuperador
from verdade_ou_fake.vocabulario import carregar_vocabulario

registro = logging.getLogger("verdade_ou_fake")
JANELA_SEGUNDOS = 60


class Entrada(BaseModel):
    entrada: str = Field(min_length=8, max_length=20000)


class Feedback(BaseModel):
    consulta_id: int
    valor: int = Field(ge=-1, le=1)


class LimiteDeRequisicoes:
    def __init__(self, por_minuto: int):
        self._por_minuto = por_minuto
        self._acessos: dict[str, deque] = defaultdict(deque)

    def permitir(self, cliente: str) -> bool:
        agora = time.monotonic()
        fila = self._acessos[cliente]
        while fila and agora - fila[0] > JANELA_SEGUNDOS:
            fila.popleft()
        if len(fila) >= self._por_minuto:
            return False
        fila.append(agora)
        return True


def criar_servico(config: Config) -> rag.Servico:
    banco = Banco(config.banco)
    embutir = criar_embutidor(config.modelo_embedding)
    llm = (
        ClienteLLM(
            config.llm_base_url,
            config.llm_api_key,
            config.llm_modelos,
            config.llm_timeout,
            esforco=config.llm_esforco,
        )
        if config.llm_ativo
        else None
    )
    return rag.Servico(
        config=config,
        banco=banco,
        recuperador=Recuperador(banco, embutir),
        embutir=embutir,
        vocabulario=carregar_vocabulario(config.vocabulario),
        llm=llm,
        versao_base=ler_manifesto(config.manifesto).get("sha256", ""),
    )


def _aquecer(servico: rag.Servico) -> None:
    config = servico.config
    if servico.banco.total_documentos() == 0 and config.base_jsonl.exists():
        registro.info("Base vazia: indexando %s", config.base_jsonl)
        construir(servico.banco, servico.embutir, config.base_jsonl)
    servico.recuperador.buscar("ivermectin covid-19", k=1)
    servico.calcular_estilo = sinal_estilo.carregar()
    registro.info("Serviço pronto: %d documentos", servico.banco.total_documentos())


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    servico = getattr(app.state, "servico", None)
    if servico is None:
        carregar_env()
        servico = criar_servico(Config())
    app.state.servico = servico
    app.state.limite = LimiteDeRequisicoes(servico.config.limite_por_minuto)
    threading.Thread(target=_aquecer, args=(servico,), daemon=True).start()
    yield
    if servico.llm is not None:
        await servico.llm.fechar()
    servico.banco.fechar()


app = FastAPI(title="Verdade ou Fake?", lifespan=ciclo_de_vida)


def _cliente(request: Request) -> str:
    encaminhado = request.headers.get("x-forwarded-for", "")
    return encaminhado.split(",")[0].strip() or (request.client.host if request.client else "?")


@app.post("/api/analisar")
async def analisar(dados: Entrada, request: Request) -> StreamingResponse:
    if not request.app.state.limite.permitir(_cliente(request)):
        raise HTTPException(429, "Muitas consultas em pouco tempo. Aguarde um minuto.")
    servico = request.app.state.servico

    async def eventos():
        try:
            async for evento in rag.analisar(servico, dados.entrada):
                yield f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            raise
        except Exception:
            registro.exception("Falha ao analisar")
            erro = {"tipo": "erro", "mensagem": "Erro interno ao analisar. Tente de novo."}
            yield f"data: {json.dumps(erro, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        eventos(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/feedback")
async def feedback(dados: Feedback, request: Request) -> dict:
    if not request.app.state.servico.banco.registrar_feedback(dados.consulta_id, dados.valor):
        raise HTTPException(404, "Consulta não encontrada.")
    return {"ok": True}


@app.get("/api/saude")
async def saude(request: Request) -> dict:
    servico = request.app.state.servico
    manifesto = ler_manifesto(servico.config.manifesto)
    return {
        "status": "ok",
        "documentos": servico.banco.total_documentos(),
        "llm": servico.llm is not None,
        "modelos": servico.config.llm_modelos if servico.llm else [],
        "sinal_estilo": servico.calcular_estilo is not None,
        "base": {k: manifesto.get(k) for k in ("gerado_em", "artigos", "sha256")},
    }


@app.get("/api/metricas")
async def metricas(request: Request) -> dict:
    return request.app.state.servico.banco.metricas()


_config = Config()
if _config.web.is_dir():
    app.mount("/", StaticFiles(directory=_config.web, html=True), name="web")

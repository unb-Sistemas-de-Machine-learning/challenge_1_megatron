import json
import re
from collections.abc import AsyncIterator

import httpx

CODIGOS_PARA_TENTAR_OUTRO = {404, 408, 413, 429, 500, 502, 503, 504}
PENSAMENTO = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


class LLMIndisponivel(RuntimeError):
    pass


class ClienteLLM:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        modelos: list[str],
        timeout: float = 45.0,
        transporte: httpx.AsyncBaseTransport | None = None,
    ):
        self.modelos = modelos
        self.ultimo_modelo: str | None = None
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(timeout, connect=8.0),
            transport=transporte,
        )

    async def fechar(self) -> None:
        await self._http.aclose()

    def _ordem(self, preferido: str | None) -> list[str]:
        if not preferido:
            return self.modelos
        return [preferido] + [m for m in self.modelos if m != preferido]

    async def completar(
        self,
        mensagens: list[dict],
        modelo: str | None = None,
        max_tokens: int = 300,
        formato_json: bool = False,
    ) -> str:
        ultimo_erro: Exception | None = None
        for nome in self._ordem(modelo):
            corpo = {
                "model": nome,
                "messages": mensagens,
                "temperature": 0,
                "max_tokens": max_tokens,
            }
            if formato_json:
                corpo["response_format"] = {"type": "json_object"}
            try:
                resposta = await self._http.post("/chat/completions", json=corpo)
                if resposta.status_code in CODIGOS_PARA_TENTAR_OUTRO:
                    ultimo_erro = LLMIndisponivel(f"{nome}: HTTP {resposta.status_code}")
                    continue
                resposta.raise_for_status()
                self.ultimo_modelo = nome
                conteudo = resposta.json()["choices"][0]["message"].get("content") or ""
                return PENSAMENTO.sub("", conteudo).strip()
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as erro:
                ultimo_erro = erro
        raise LLMIndisponivel(str(ultimo_erro))

    async def transmitir(
        self, mensagens: list[dict], max_tokens: int = 600
    ) -> AsyncIterator[str]:
        ultimo_erro: Exception | None = None
        for nome in self.modelos:
            corpo = {
                "model": nome,
                "messages": mensagens,
                "temperature": 0.1,
                "max_tokens": max_tokens,
                "stream": True,
            }
            entregou = False
            try:
                async with self._http.stream("POST", "/chat/completions", json=corpo) as resposta:
                    if resposta.status_code in CODIGOS_PARA_TENTAR_OUTRO:
                        ultimo_erro = LLMIndisponivel(f"{nome}: HTTP {resposta.status_code}")
                        continue
                    resposta.raise_for_status()
                    self.ultimo_modelo = nome
                    async for pedaco in _sem_pensamento(_ler_sse(resposta)):
                        entregou = True
                        yield pedaco
                return
            except (httpx.HTTPError, ValueError) as erro:
                ultimo_erro = erro
                if entregou:
                    return
        raise LLMIndisponivel(str(ultimo_erro))


async def _ler_sse(resposta: httpx.Response) -> AsyncIterator[str]:
    async for linha in resposta.aiter_lines():
        if not linha.startswith("data:"):
            continue
        dado = linha[5:].strip()
        if dado == "[DONE]":
            return
        try:
            escolhas = json.loads(dado).get("choices") or []
        except (json.JSONDecodeError, AttributeError):
            continue
        if escolhas and (texto := (escolhas[0].get("delta") or {}).get("content")):
            yield texto


async def _sem_pensamento(pedacos: AsyncIterator[str]) -> AsyncIterator[str]:
    acumulado = ""
    decidido = False
    aparar_inicio = False
    async for pedaco in pedacos:
        if decidido:
            if aparar_inicio:
                pedaco = pedaco.lstrip()
                if not pedaco:
                    continue
                aparar_inicio = False
            yield pedaco
            continue
        acumulado += pedaco
        inicio = acumulado.lstrip()
        if "<think>".startswith(inicio[:7]) and len(inicio) < 7:
            continue
        if inicio.startswith("<think>"):
            if "</think>" not in inicio:
                continue
            resto = inicio.split("</think>", 1)[1].lstrip()
            decidido = True
            if resto:
                yield resto
            else:
                aparar_inicio = True
        else:
            decidido = True
            yield acumulado
    if not decidido and acumulado and not acumulado.lstrip().startswith("<think>"):
        yield acumulado

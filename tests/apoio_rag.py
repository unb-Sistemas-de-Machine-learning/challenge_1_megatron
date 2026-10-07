import json
import re

import httpx
import numpy as np

from verdade_ou_fake import rag
from verdade_ou_fake.banco import Banco
from verdade_ou_fake.base import indexar
from verdade_ou_fake.config import Config
from verdade_ou_fake.llm import ClienteLLM
from verdade_ou_fake.recuperacao import Recuperador

VOCABULARIO_VETORIAL = [
    "ivermectin", "ivermectina", "covid", "vitamin", "vitamina", "influenza", "gripe",
    "metformin", "metformina", "diabetes", "economia", "ministro",
]  # fmt: skip
SINONIMOS = {"ivermectina": "ivermectin", "vitamina": "vitamin", "gripe": "influenza", "metformina": "metformin"}

DOCUMENTOS = [
    {
        "fonte": "pubmed", "id_externo": "1", "ano": 2022, "tipos": ["Meta-Analysis"],
        "titulo": "Ivermectin for COVID-19: a meta-analysis",
        "texto": "Ivermectin did not reduce mortality in covid patients.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/1/",
    },
    {
        "fonte": "pubmed", "id_externo": "2", "ano": 2021, "tipos": ["Randomized Controlled Trial"],
        "titulo": "Ivermectin in mild covid: randomized trial",
        "texto": "Ivermectin showed no benefit for covid symptoms.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/2/",
    },
    {
        "fonte": "pubmed", "id_externo": "3", "ano": 2019, "tipos": ["Journal Article"],
        "titulo": "Metformin and diabetes outcomes",
        "texto": "Metformin improves glycemic control in diabetes.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/3/",
    },
]  # fmt: skip


def embutir_falso(textos: list[str]) -> np.ndarray:
    vetores = np.zeros((len(textos), len(VOCABULARIO_VETORIAL)), dtype=np.float32)
    for linha, texto in enumerate(textos):
        for palavra in re.findall(r"[a-z]+", texto.lower()):
            palavra = SINONIMOS.get(palavra, palavra)
            if palavra in VOCABULARIO_VETORIAL:
                vetores[linha, VOCABULARIO_VETORIAL.index(palavra)] += 1
    normas = np.linalg.norm(vetores, axis=1, keepdims=True)
    return vetores / np.clip(normas, 1e-9, None)


def sse(texto: str, tamanho: int = 7) -> bytes:
    pedacos = [texto[i : i + tamanho] for i in range(0, len(texto), tamanho)]
    linhas = [
        "data: " + json.dumps({"choices": [{"delta": {"content": p}}]}) for p in pedacos
    ]
    return ("\n\n".join(linhas) + "\n\ndata: [DONE]\n\n").encode()


class LLMFalso:
    def __init__(self, alegacao: dict | None, redacao: str | None, status: int = 200):
        self.alegacao = alegacao
        self.redacao = redacao
        self.status = status
        self.chamadas: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.content)
        self.chamadas.append(corpo)
        if self.status != 200:
            return httpx.Response(self.status)
        if corpo.get("stream"):
            return httpx.Response(200, content=sse(self.redacao or ""))
        conteudo = json.dumps(self.alegacao) if self.alegacao is not None else "isto não é json"
        return httpx.Response(200, json={"choices": [{"message": {"content": conteudo}}]})


ALEGACAO_IVERMECTINA = {
    "saude": True,
    "alegacao": "Ivermectina cura covid-19",
    "consulta_en": "ivermectin for the treatment of covid",
    "pubmed": "ivermectin AND covid",
}
REDACAO_CONTESTADA = (
    "VEREDITO: CONTESTADA\nCONFIANCA: alta\nRESUMO: Os estudos não mostram benefício.\n---\n"
    "A meta-análise não encontrou redução de mortalidade [1]. "
    "Um ensaio também não viu melhora [2][9]."
)


def criar_servico(llm_falso: LLMFalso | None = None, documentos=DOCUMENTOS, **extras) -> rag.Servico:
    banco = Banco(":memory:")
    indexar(banco, embutir_falso, list(documentos), origem="lote")
    llm = None
    if llm_falso is not None:
        llm = ClienteLLM(
            "http://llm.teste", "chave", ["modelo-a"], transporte=httpx.MockTransport(llm_falso)
        )
    opcoes = {
        "config": Config(),
        "banco": banco,
        "recuperador": Recuperador(banco, embutir_falso),
        "embutir": embutir_falso,
        "vocabulario": {
            "medicamento": [("ivermectina", "Ivermectin"), ("metformina", "Metformin")],
            "condicao": [("covid", "COVID"), ("diabetes", "Diabetes")],
        },
        "llm": llm,
        "versao_base": "v1",
        "extrair_noticia": lambda url: None,
        "buscar_ao_vivo": lambda termo: [],
    }
    opcoes.update(extras)
    return rag.Servico(**opcoes)

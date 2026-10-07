"""Configuração do serviço, toda por variável de ambiente.

O LLM é qualquer servidor compatível com a API de chat da OpenAI. Trocar de
provedor é trocar três variáveis, sem tocar no código:

    Groq (padrão)   LLM_BASE_URL=https://api.groq.com/openai/v1
    Gemini          LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
    Ollama (local)  LLM_BASE_URL=http://localhost:11434/v1   LLM_API_KEY=ollama

Sem LLM_API_KEY o serviço sobe em modo degradado: recupera e mostra as fontes,
mas não redige o veredito.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _lista(valor: str) -> list[str]:
    return [item.strip() for item in valor.split(",") if item.strip()]


@dataclass(frozen=True)
class Config:
    banco: Path = field(
        default_factory=lambda: Path(os.environ.get("VOF_BANCO", RAIZ / "dados" / "vof.db"))
    )
    base_jsonl: Path = RAIZ / "dados" / "base" / "pubmed.jsonl"
    manifesto: Path = RAIZ / "dados" / "base" / "manifesto.json"
    vocabulario: Path = RAIZ / "dados" / "vocabulario_seed.csv"
    web: Path = RAIZ / "web"

    llm_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "LLM_BASE_URL", "https://api.groq.com/openai/v1"
        ).rstrip("/")
    )
    llm_api_key: str = field(
        default_factory=lambda: os.environ.get("LLM_API_KEY") or os.environ.get("GROQ_API_KEY", "")
    )
    # Tentados em ordem: se um modelo estoura a cota gratuita (HTTP 429) ou
    # falha, o próximo assume. Somar as cotas é o que sustenta uma demo.
    llm_modelos: list[str] = field(
        default_factory=lambda: _lista(
            os.environ.get(
                "LLM_MODELOS",
                "llama-3.3-70b-versatile,openai/gpt-oss-120b,llama-3.1-8b-instant",
            )
        )
    )
    # Modelo pequeno para a etapa de entender a alegação (JSON curto).
    llm_modelo_rapido: str = field(
        default_factory=lambda: os.environ.get("LLM_MODELO_RAPIDO", "llama-3.1-8b-instant")
    )

    modelo_embedding: str = field(
        default_factory=lambda: os.environ.get(
            "VOF_MODELO_EMBEDDING",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
    )
    fontes_por_resposta: int = 5
    # Abaixo disso a base local não cobre a alegação e vale a ida ao PubMed.
    similaridade_minima: float = float(os.environ.get("VOF_SIMILARIDADE_MINIMA", "0.45"))
    cache_horas: int = int(os.environ.get("VOF_CACHE_HORAS", "168"))
    limite_por_minuto: int = int(os.environ.get("VOF_LIMITE_POR_MINUTO", "12"))
    busca_ao_vivo: bool = os.environ.get("VOF_BUSCA_AO_VIVO", "1") != "0"

    @property
    def llm_ativo(self) -> bool:
        return bool(self.llm_api_key and self.llm_modelos)

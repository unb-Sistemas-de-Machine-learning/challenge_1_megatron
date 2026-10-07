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
    llm_modelos: list[str] = field(
        default_factory=lambda: _lista(
            os.environ.get(
                "LLM_MODELOS",
                "llama-3.3-70b-versatile,openai/gpt-oss-120b,llama-3.1-8b-instant",
            )
        )
    )
    llm_modelo_rapido: str = field(
        default_factory=lambda: os.environ.get("LLM_MODELO_RAPIDO", "llama-3.1-8b-instant")
    )

    llm_timeout: float = field(
        default_factory=lambda: float(os.environ.get("LLM_TIMEOUT", "45"))
    )
    modelo_embedding: str = field(
        default_factory=lambda: os.environ.get(
            "VOF_MODELO_EMBEDDING",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
    )
    fontes_por_resposta: int = 5
    similaridade_minima: float = field(
        default_factory=lambda: float(os.environ.get("VOF_SIMILARIDADE_MINIMA", "0.45"))
    )
    cache_horas: int = field(default_factory=lambda: int(os.environ.get("VOF_CACHE_HORAS", "168")))
    limite_por_minuto: int = field(
        default_factory=lambda: int(os.environ.get("VOF_LIMITE_POR_MINUTO", "12"))
    )
    busca_ao_vivo: bool = field(
        default_factory=lambda: os.environ.get("VOF_BUSCA_AO_VIVO", "1") != "0"
    )

    @property
    def llm_ativo(self) -> bool:
        return bool(self.llm_api_key and self.llm_modelos)

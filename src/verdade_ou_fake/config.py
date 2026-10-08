import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def carregar_env(caminho: Path | None = None) -> None:
    caminho = caminho or RAIZ / ".env"
    if not caminho.is_file():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        nome, _, valor = linha.partition("=")
        os.environ.setdefault(nome.strip(), valor.strip().strip("'\""))


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
                "openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b",
            )
        )
    )
    llm_modelo_rapido: str = field(
        default_factory=lambda: os.environ.get("LLM_MODELO_RAPIDO", "openai/gpt-oss-20b")
    )

    llm_esforco: str = field(
        default_factory=lambda: os.environ.get("LLM_ESFORCO_RACIOCINIO", "low")
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

    planilha_csv: str = field(default_factory=lambda: os.environ.get("VOF_PLANILHA_CSV", ""))
    destaques_automaticos: bool = field(
        default_factory=lambda: os.environ.get("VOF_DESTAQUES_AUTOMATICOS", "1") != "0"
    )
    destaques_maximo: int = field(
        default_factory=lambda: int(os.environ.get("VOF_DESTAQUES_MAXIMO", "6"))
    )
    destaques_horas: float = field(
        default_factory=lambda: float(os.environ.get("VOF_DESTAQUES_HORAS", "6"))
    )
    destaques_pausa: float = field(
        default_factory=lambda: float(os.environ.get("VOF_DESTAQUES_PAUSA", "25"))
    )

    @property
    def llm_ativo(self) -> bool:
        return bool(self.llm_api_key and self.llm_modelos)

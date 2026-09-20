from dataclasses import dataclass, field


@dataclass
class Noticia:
    url: str
    titulo: str
    texto: str
    dominio: str


@dataclass
class Alegacao:
    medicamento_pt: str
    medicamento_en: str
    condicao_pt: str
    condicao_en: str


@dataclass
class Artigo:
    pmid: str
    titulo: str
    resumo: str
    tipos_estudo: list[str]
    ano: int | None


@dataclass
class Evidencia:
    cobertura: str
    forca: str
    artigos: list[Artigo] = field(default_factory=list)


@dataclass
class Veredito:
    rotulo: str
    confianca: str
    risco_textual: float
    alegacao: Alegacao | None
    evidencia: Evidencia | None
    explicacao: str

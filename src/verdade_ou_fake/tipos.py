from dataclasses import dataclass


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

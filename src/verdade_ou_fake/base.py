import json
from pathlib import Path

from verdade_ou_fake.banco import Banco
from verdade_ou_fake.embeddings import Embutidor
from verdade_ou_fake.tipos import Artigo

FONTE_PUBMED = "pubmed"
LOTE = 64


def documento_de_artigo(artigo: Artigo) -> dict:
    return {
        "fonte": FONTE_PUBMED,
        "id_externo": artigo.pmid,
        "titulo": artigo.titulo,
        "texto": artigo.resumo,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{artigo.pmid}/",
        "ano": artigo.ano,
        "tipos": artigo.tipos_estudo,
    }


def texto_para_embedding(documento: dict) -> str:
    return f"{documento['titulo']} {documento['texto']}"[:2000]


def indexar(banco: Banco, embutir: Embutidor, documentos: list[dict], origem: str) -> int:
    existentes = banco.ids_existentes(FONTE_PUBMED)
    novos = [d for d in documentos if d["id_externo"] not in existentes]
    inseridos = 0
    for inicio in range(0, len(novos), LOTE):
        lote = novos[inicio : inicio + LOTE]
        vetores = embutir([texto_para_embedding(d) for d in lote])
        inseridos += banco.inserir_documentos(lote, vetores, origem=origem)
    return inseridos


def ler_jsonl(caminho: Path) -> list[dict]:
    documentos = []
    with open(caminho, encoding="utf-8") as arquivo:
        for linha in arquivo:
            if not linha.strip():
                continue
            item = json.loads(linha)
            documentos.append(
                documento_de_artigo(
                    Artigo(
                        pmid=item["pmid"],
                        titulo=item["titulo"],
                        resumo=item["resumo"],
                        tipos_estudo=item.get("tipos_estudo", []),
                        ano=item.get("ano"),
                    )
                )
            )
    return documentos


def construir(banco: Banco, embutir: Embutidor, caminho_jsonl: Path) -> int:
    return indexar(banco, embutir, ler_jsonl(caminho_jsonl), origem="lote")


def ler_manifesto(caminho: Path) -> dict:
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))

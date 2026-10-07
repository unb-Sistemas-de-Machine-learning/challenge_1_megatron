import argparse
import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.evidencia import FILTRO_ESTUDOS_FORTES, baixar_artigos, buscar_pmids  # noqa: E402

CAMINHO_VOCABULARIO = RAIZ / "dados" / "vocabulario_seed.csv"
SAIDA = RAIZ / "dados" / "base" / "pubmed.jsonl"
MANIFESTO = RAIZ / "dados" / "base" / "manifesto.json"
ARTIGOS_POR_PAR = 6
ARTIGOS_POR_MEDICAMENTO = 12
LOTE_EFETCH = 150


def ler_termos(caminho: Path) -> tuple[list[str], list[str]]:
    medicamentos, condicoes = [], []
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            destino = medicamentos if linha["tipo"] == "medicamento" else condicoes
            if linha["termo_en"] not in destino:
                destino.append(linha["termo_en"])
    return medicamentos, condicoes


def montar_consultas(medicamentos: list[str], condicoes: list[str]) -> list[tuple[str, int]]:
    consultas = [
        (f'"{m}"[Title/Abstract] AND {FILTRO_ESTUDOS_FORTES}', ARTIGOS_POR_MEDICAMENTO)
        for m in medicamentos
    ]
    consultas += [
        (
            f'"{m}"[Title/Abstract] AND "{c}"[Title/Abstract] AND {FILTRO_ESTUDOS_FORTES}',
            ARTIGOS_POR_PAR,
        )
        for m in medicamentos
        for c in condicoes
    ]
    return consultas


def sha256_do_arquivo(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestão em lote da base de conhecimento do RAG a partir do PubMed")
    parser.add_argument("--limite", type=int, help="roda só as N primeiras consultas")
    args = parser.parse_args()

    consultas = montar_consultas(*ler_termos(CAMINHO_VOCABULARIO))
    if args.limite:
        consultas = consultas[: args.limite]

    pmids: dict[str, None] = {}
    falhas = 0
    for i, (termo, quantos) in enumerate(consultas, 1):
        try:
            for pmid in buscar_pmids(termo, quantos):
                pmids[pmid] = None
        except Exception as erro:
            falhas += 1
            print(f"  falha em {termo[:60]}: {erro}", file=sys.stderr)
        if i % 25 == 0:
            print(f"{i}/{len(consultas)} consultas, {len(pmids)} artigos únicos", flush=True)

    ids = list(pmids)
    artigos = []
    for inicio in range(0, len(ids), LOTE_EFETCH):
        try:
            artigos += baixar_artigos(ids[inicio : inicio + LOTE_EFETCH])
        except Exception as erro:
            falhas += 1
            print(f"  falha no lote {inicio}: {erro}", file=sys.stderr)
        print(f"baixados {len(artigos)}/{len(ids)}", flush=True)

    artigos = [a for a in artigos if a.pmid and len(a.resumo) >= 200]
    artigos.sort(key=lambda a: int(a.pmid))

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as arquivo:
        for a in artigos:
            linha = {
                "pmid": a.pmid,
                "titulo": a.titulo,
                "resumo": a.resumo,
                "tipos_estudo": a.tipos_estudo,
                "ano": a.ano,
            }
            arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")

    manifesto = {
        "fonte": "PubMed E-utilities",
        "gerado_em": date.today().isoformat(),
        "consultas": len(consultas),
        "falhas": falhas,
        "artigos": len(artigos),
        "sha256": sha256_do_arquivo(SAIDA),
        "script": "scripts/ingere_pubmed.py",
    }
    MANIFESTO.write_text(json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifesto, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent

ARQUIVOS_DO_SPACE = [
    "Dockerfile",
    ".dockerignore",
    "requirements.txt",
    "src",
    "web",
    "scripts/__init__.py",
    "scripts/constroi_base.py",
    "dados/base",
    "dados/vocabulario_seed.csv",
    "modelos/cards",
]

README_SPACE = """---
title: Verdade ou Fake?
emoji: 🔍
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Checagem de notícias sobre medicamentos e tratamentos
---

# Verdade ou Fake?

Detecção de desinformação em notícias de saúde — Equipe Megatron,
Sistemas de Machine Learning (UnB/FCTE), 2026/2.

Código-fonte e documentação: https://github.com/unb-Sistemas-de-Machine-learning/challenge_1_megatron

**Este sistema é apenas informativo e não substitui orientação médica.**
"""


def montar_pasta_space(raiz: Path, destino: Path) -> None:
    for relativo in ARQUIVOS_DO_SPACE:
        origem = raiz / relativo
        alvo = destino / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if origem.is_dir():
            shutil.copytree(origem, alvo, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(origem, alvo)
    (destino / "README.md").write_text(README_SPACE, encoding="utf-8")


def conferir_base(raiz: Path) -> None:
    jsonl = raiz / "dados" / "base" / "pubmed.jsonl"
    manifesto = raiz / "dados" / "base" / "manifesto.json"
    for caminho in (jsonl, manifesto):
        if not caminho.exists():
            raise ValueError(f"Base de conhecimento incompleta: {caminho} não encontrado.")
    esperado = json.loads(manifesto.read_text(encoding="utf-8")).get("sha256")
    obtido = hashlib.sha256(jsonl.read_bytes()).hexdigest()
    if obtido != esperado:
        raise ValueError(
            f"O SHA-256 de pubmed.jsonl ({obtido}) não bate com o do manifesto ({esperado})."
        )


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Publica o app num Hugging Face Space (SDK Docker)")
    argumentos.add_argument("space_id", help="Space de destino, ex.: equipe/verdade-ou-fake")
    args = argumentos.parse_args()

    try:
        conferir_base(RAIZ)
    except ValueError as erro:
        print(f"Erro: {erro}")
        return 1

    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(args.space_id, repo_type="space", space_sdk="docker", exist_ok=True)
    with tempfile.TemporaryDirectory() as pasta:
        montar_pasta_space(RAIZ, Path(pasta))
        api.upload_folder(
            repo_id=args.space_id,
            repo_type="space",
            folder_path=pasta,
            commit_message="Deploy do app",
        )
    print(f"App publicado em https://huggingface.co/spaces/{args.space_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Publica o app num Hugging Face Space (SDK Docker).

O Space recebe só o necessário para servir o app: código, vocabulário, model
cards, Dockerfile e requirements. Os pesos do BERTimbau vêm do Hub em tempo de
execução (VOF_MODELO_RISCO, configurada nos secrets/variáveis do Space).

Recusa publicar se o card do BERTimbau não estiver em `producao`: o app
subiria só para exibir erro.

Pré-requisito: `hf auth login` (ou HF_TOKEN no ambiente) com permissão de escrita.

Uso: python scripts/publica_space.py <usuario>/<space>
"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.model_card import carregar_card

CAMINHO_CARD = RAIZ / "modelos" / "cards" / "bertimbau.json"

ARQUIVOS_DO_SPACE = [
    "Dockerfile",
    ".dockerignore",
    "requirements.txt",
    "app.py",
    "src/verdade_ou_fake",
    "dados/vocabulario_seed.csv",
    "modelos/cards",
]

# Metadados que o Hugging Face lê do README.md do Space.
README_SPACE = """---
title: Verdade ou Fake?
emoji: 🔍
colorFrom: green
colorTo: gray
sdk: docker
app_port: 8501
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
    """Copia para `destino` os arquivos do Space e escreve o README com metadados."""
    for relativo in ARQUIVOS_DO_SPACE:
        origem = raiz / relativo
        alvo = destino / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if origem.is_dir():
            shutil.copytree(origem, alvo, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(origem, alvo)
    (destino / "README.md").write_text(README_SPACE, encoding="utf-8")


def conferir_card_de_producao(caminho_card: Path) -> None:
    """Levanta ValueError se o card não autorizar o modelo a ir ao ar."""
    if not caminho_card.exists():
        raise ValueError(f"Model card não encontrado em {caminho_card}.")
    status = carregar_card(caminho_card)["status"]
    if status != "producao":
        raise ValueError(
            f"O model card do BERTimbau está em '{status}'. Revise as métricas e promova-o "
            "manualmente a 'producao' antes de publicar o app."
        )


def main() -> int:
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("space_id", help="Space de destino, ex.: equipe/verdade-ou-fake")
    args = argumentos.parse_args()

    try:
        conferir_card_de_producao(CAMINHO_CARD)
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

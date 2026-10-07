import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.model_card import calcular_hash_artefato, carregar_card
from verdade_ou_fake.modelo_producao import ARQUIVO_PESOS

CAMINHO_MODELO = RAIZ / "modelos" / "bertimbau"
CAMINHO_CARD = RAIZ / "modelos" / "cards" / "bertimbau.json"


def conferir_artefato(caminho_modelo: Path, caminho_card: Path) -> dict:
    pesos = caminho_modelo / ARQUIVO_PESOS
    if not pesos.exists():
        raise ValueError(f"Pesos não encontrados em {pesos}. Rode scripts/treina_bert.py.")
    if not caminho_card.exists():
        raise ValueError(f"Model card não encontrado em {caminho_card}. Rode scripts/treina_bert.py.")

    card = carregar_card(caminho_card)
    if calcular_hash_artefato(pesos) != card["artefato_hash_sha256"]:
        raise ValueError(
            "Os pesos locais não correspondem ao model card — regenere o card com "
            "`python scripts/treina_bert.py --somente-avaliar` antes de publicar."
        )
    return card


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Publica o BERTimbau treinado num repositório de modelo do Hugging Face Hub")
    argumentos.add_argument("repo_id", help="repositório de destino, ex.: equipe/bertimbau-saude")
    argumentos.add_argument("--privado", action="store_true", help="cria o repositório como privado")
    args = argumentos.parse_args()

    try:
        card = conferir_artefato(CAMINHO_MODELO, CAMINHO_CARD)
    except ValueError as erro:
        print(f"Erro: {erro}")
        return 1

    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(args.repo_id, repo_type="model", private=args.privado, exist_ok=True)
    commit = api.upload_folder(
        repo_id=args.repo_id,
        repo_type="model",
        folder_path=CAMINHO_MODELO,
        ignore_patterns=["_checkpoints/*"],
        commit_message=f"BERTimbau {card['versao']} (sha256 {card['artefato_hash_sha256'][:12]})",
    )
    print(f"Modelo publicado em https://huggingface.co/{args.repo_id}")
    print("Configure no ambiente de produção:")
    print(f"  VOF_MODELO_RISCO={args.repo_id}")
    print(f"  VOF_MODELO_RISCO_REVISAO={commit.oid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

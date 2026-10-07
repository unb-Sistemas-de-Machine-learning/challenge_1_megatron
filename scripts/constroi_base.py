import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.banco import Banco  # noqa: E402
from verdade_ou_fake.base import construir  # noqa: E402
from verdade_ou_fake.config import Config, carregar_env  # noqa: E402
from verdade_ou_fake.embeddings import criar_embutidor  # noqa: E402


def main() -> None:
    carregar_env()
    config = Config()
    if not config.base_jsonl.exists():
        sys.exit(f"Base ausente: {config.base_jsonl}. Rode scripts/ingere_pubmed.py.")
    inicio = time.monotonic()
    banco = Banco(config.banco)
    inseridos = construir(banco, criar_embutidor(config.modelo_embedding), config.base_jsonl)
    print(
        f"{inseridos} documentos indexados, {banco.total_documentos()} no total, "
        f"em {time.monotonic() - inicio:.0f}s -> {config.banco}"
    )
    banco.fechar()


if __name__ == "__main__":
    main()

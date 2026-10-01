"""Verifica se um model card passa no gate de qualidade — usado pelo CI.

Uso: python scripts/verifica_gate.py modelos/cards/baseline.json
Saída: código 0 se aprovado, 1 se reprovado.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.model_card import aprovar_gate, carregar_card


def main(caminho_card: str) -> int:
    card = carregar_card(Path(caminho_card))
    aprovado = aprovar_gate(card)
    if aprovado:
        print(f"Gate aprovado: F1 same-source = {card['metricas']['f1_macro_same_source']:.3f}")
        return 0
    print(f"Gate reprovado: {card['metricas']}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

"""Verifica se um model card passa no gate de qualidade — usado pelo CI.

Uso: python scripts/verifica_gate.py modelos/cards/baseline.json
Saída: código 0 se aprovado, 1 se reprovado.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.model_card import aprovar_gate, carregar_card


def _formatar_cross_source(valor: float | None) -> str:
    """Formata uma métrica cross-source, cobrindo o caso de não avaliada (None)."""
    return "não avaliado" if valor is None else f"{valor:.3f}"


def main(caminho_card: str) -> int:
    card = carregar_card(Path(caminho_card))
    aprovado = aprovar_gate(card)
    metricas = card["metricas"]
    if aprovado:
        cross_a = _formatar_cross_source(metricas["f1_macro_cross_source_fakebr_para_fakerecogna"])
        cross_b = _formatar_cross_source(metricas["f1_macro_cross_source_fakerecogna_para_fakebr"])
        print(
            f"Gate aprovado: F1 same-source = {metricas['f1_macro_same_source']:.3f}, "
            f"F1 cross-source (fakebr->fakerecogna) = {cross_a}, "
            f"F1 cross-source (fakerecogna->fakebr) = {cross_b}"
        )
        return 0
    print(f"Gate reprovado: {metricas}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1]))
    except IndexError as e:
        print(f"Erro: caminho do model card não informado. Uso: python scripts/verifica_gate.py <caminho.json> ({e})")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Erro: model card não encontrado: {e}")
        sys.exit(1)
    except KeyError as e:
        print(f"Erro: model card malformado, campo ausente: {e}")
        sys.exit(1)

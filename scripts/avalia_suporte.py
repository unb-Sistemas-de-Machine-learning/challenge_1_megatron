"""Avalia a acurácia do zero-shot da etapa [2c] antes de decidir sobre fine-tuning (Task 12).

Roda `classificar_suporte` (modelo real, sem mock) contra pares resumo+alegação
extraídos de artigos reais do PubMed e anotados manualmente em
`dados/avaliacao/suporte_pubmed.json`. Segue a recomendação da Task 11 do plano:
"rodar classificar_suporte sobre 50-100 pares anotados manualmente e medir
acurácia. Se acurácia >= 0.75, o zero-shot é suficiente para a Fase 2."

Uso: python scripts/avalia_suporte.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.suporte import classificar_suporte

CAMINHO_CASOS = RAIZ / "dados" / "avaliacao" / "suporte_pubmed.json"
LIMIAR_SUFICIENTE = 0.75


def main() -> None:
    casos = json.loads(CAMINHO_CASOS.read_text(encoding="utf-8"))
    print(f"Avaliando {len(casos)} pares resumo+alegação anotados manualmente...\n")

    acertos = 0
    matriz: Counter[tuple[str, str]] = Counter()
    for i, caso in enumerate(casos, start=1):
        previsto = classificar_suporte(caso["resumo"], caso["alegacao"])
        esperado = caso["rotulo_esperado"]
        matriz[(esperado, previsto)] += 1
        if previsto == esperado:
            acertos += 1
        else:
            print(f"[{i}/{len(casos)}] divergência — esperado={esperado} previsto={previsto} "
                  f"(pmid {caso['pmid']}, {caso['alegacao']})")

    acuracia = acertos / len(casos)
    print(f"\n=== Acurácia geral: {acuracia:.1%} ({acertos}/{len(casos)}) ===\n")

    print("Matriz esperado -> previsto:")
    rotulos = ["apoia", "contradiz", "nao_determinado"]
    for esperado in rotulos:
        linha = {previsto: matriz.get((esperado, previsto), 0) for previsto in rotulos}
        print(f"  {esperado:16s} {linha}")

    if acuracia >= LIMIAR_SUFICIENTE:
        print(
            f"\nAcurácia >= {LIMIAR_SUFICIENTE:.0%}: o zero-shot é suficiente para a Fase 2. "
            "Task 12 (fine-tuning do mDeBERTa) não é necessária por este critério."
        )
    else:
        print(
            f"\nAcurácia < {LIMIAR_SUFICIENTE:.0%}: por este critério, valeria considerar a "
            "Task 12 (fine-tuning do mDeBERTa)."
        )


if __name__ == "__main__":
    main()

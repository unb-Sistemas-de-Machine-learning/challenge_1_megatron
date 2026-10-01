"""Fine-tuning exploratório da etapa [2c] e comparação com o zero-shot (Task 12).

Critério de entrada satisfeito: `scripts/avalia_suporte.py` mediu 48,1% de
acurácia zero-shot nos 79 pares de `dados/avaliacao/suporte_pubmed.json`
(limiar de confiança recalibrado para 0,75 — ver `suporte.py`), abaixo dos
75% do plano. Ver as limitações desta implementação (sem MedNLI, só a
cabeça de classificação é treinada) em `suporte_treino.py`.

Divide os 79 pares em treino/teste (80/20, estratificado por rótulo) para que
a comparação de acurácia com o zero-shot seja honesta — sem isso, medir no
próprio conjunto de treino infla o resultado.

Aviso sobre o teste ficar pequeno (~16 exemplos): uma diferença de 1 acerto já
move a acurácia em ~6 pontos percentuais. Por isso o critério de "melhorou"
abaixo exige uma margem maior que isso para significar algo, não qualquer
`>` na comparação bruta.

Uso: python scripts/treina_suporte.py
"""

import json
import sys
from pathlib import Path

import torch
from sklearn.model_selection import train_test_split

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.suporte_treino import ROTULO_PARA_ID, construir_modelo_treinavel, treinar_suporte

CAMINHO_CASOS = RAIZ / "dados" / "avaliacao" / "suporte_pubmed.json"
CAMINHO_MODELO = RAIZ / "modelos" / "suporte_finetuned"
ACURACIA_ZERO_SHOT = 0.481  # scripts/avalia_suporte.py, limiar=0.75
MARGEM_MINIMA_PARA_CONSIDERAR_MELHORA = 0.10  # ~2 acertos a mais em 16 exemplos de teste


def _prever(modelo, tokenizer, resumo: str, alegacao_texto: str) -> str:
    modelo.eval()
    entradas = tokenizer(resumo, alegacao_texto, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        logits = modelo(**entradas).logits
    id_previsto = int(torch.argmax(logits, dim=-1)[0])
    id_para_rotulo = {v: k for k, v in ROTULO_PARA_ID.items()}
    return id_para_rotulo[id_previsto]


def main() -> None:
    casos = json.loads(CAMINHO_CASOS.read_text(encoding="utf-8"))
    casos = [c for c in casos if c["resumo"].strip()]
    rotulos = [c["rotulo_esperado"] for c in casos]

    treino, teste = train_test_split(
        casos, test_size=0.2, random_state=42, stratify=rotulos
    )
    print(f"Treino: {len(treino)} · Teste: {len(teste)}\n")

    pares_treino = [(c["resumo"], c["alegacao"], c["rotulo_esperado"]) for c in treino]

    print("Fine-tuning (backbone e pooler congelados, só a cabeça de classificação)...\n")
    treinar_suporte(pares_treino, CAMINHO_MODELO, epocas=5, tamanho_lote=4)

    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    modelo = AutoModelForSequenceClassification.from_pretrained(CAMINHO_MODELO)
    tokenizer = AutoTokenizer.from_pretrained(CAMINHO_MODELO)

    acertos = 0
    for c in teste:
        previsto = _prever(modelo, tokenizer, c["resumo"], c["alegacao"])
        if previsto == c["rotulo_esperado"]:
            acertos += 1
    acuracia = acertos / len(teste)

    print(f"=== Acurácia no conjunto de teste (fine-tuned): {acuracia:.1%} ({acertos}/{len(teste)}) ===")
    print(f"Acurácia zero-shot de referência (Task 11, 79 pares): {ACURACIA_ZERO_SHOT:.1%}\n")

    if acuracia - ACURACIA_ZERO_SHOT >= MARGEM_MINIMA_PARA_CONSIDERAR_MELHORA:
        print(
            f"O fine-tuning melhorou a acurácia por uma margem que não é só ruído "
            f"de amostra pequena. Modelo salvo em {CAMINHO_MODELO}. "
            "AVISO: treinado com 79 pares (o plano previa ~500) e sem MedNLI — "
            "tratar como resultado exploratório, não como modelo de produção pronto."
        )
    else:
        print(
            "O fine-tuning NÃO melhorou o suficiente sobre o zero-shot para distinguir "
            "de ruído — com 16 exemplos de teste, 1 acerto a mais já move o resultado em "
            "~6 pontos percentuais. Recomendação: manter o zero-shot em produção e não "
            "usar o modelo salvo em modelos/suporte_finetuned até haver mais pares "
            "anotados (o plano original previa ~500, não 79)."
        )


if __name__ == "__main__":
    main()

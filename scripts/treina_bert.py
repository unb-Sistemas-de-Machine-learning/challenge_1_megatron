"""Faz o fine-tuning do BERTimbau no recorte de saúde e compara com o baseline.

Usa a MESMA divisão treino/teste de `scripts/treina_modelo.py` (mesmo
`random_state`, mesmo agrupamento por par) para que a comparação de F1 seja
justa. Por critério da Task 10: o BERTimbau só substitui o baseline TF-IDF se
superar o F1 macro dele no conjunto de teste — ganho marginal não justifica o
custo de inferência de um modelo muito maior.

Uso: python scripts/treina_bert.py
"""

import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import GroupShuffleSplit

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.classificador import construir_modelo_bert, prever_risco_bert, treinar_bert

CAMINHO_DADOS = RAIZ / "dados" / "processed" / "saude_ptbr.csv"
CAMINHO_MODELO = RAIZ / "modelos" / "bertimbau"
LIMIAR_RISCO = 0.5

# F1 macro do baseline TF-IDF, registrado em docs/canva.md (validação cruzada
# por par, 10 dobras): 0,80 ± 0,08.
F1_BASELINE = 0.80


def main() -> None:
    df = pd.read_csv(CAMINHO_DADOS, dtype={"id_par": str})
    print(f"Notícias: {len(df)}")
    print(df["rotulo"].value_counts(), "\n")

    divisor = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    indices_treino, indices_teste = next(divisor.split(df, groups=df["id_par"]))
    treino, teste = df.iloc[indices_treino], df.iloc[indices_teste]
    treino_x, treino_y = treino["texto"].tolist(), treino["rotulo"].tolist()
    teste_x, teste_y = teste["texto"].tolist(), teste["rotulo"].tolist()

    print(f"Treino: {len(treino_x)} · Teste: {len(teste_x)}\n")
    print("Treinando BERTimbau (pode levar bastante tempo em CPU sem GPU)...\n")
    # Ambiente sem GPU e com poucos GB de RAM livres: o fine-tuning completo
    # (110M parâmetros treináveis) já foi morto pelo OOM killer do kernel uma
    # vez neste projeto. Congelar os embeddings + as 8 primeiras das 12
    # camadas do encoder e reduzir o tamanho de sequência corta a memória do
    # otimizador (Adam guarda 2 cópias extras por parâmetro treinável).
    treinar_bert(
        treino_x,
        treino_y,
        CAMINHO_MODELO,
        epocas=2,
        tamanho_lote=2,
        camadas_congeladas=8,
        tamanho_maximo_tokens=256,
    )

    modelo, tokenizer = construir_modelo_bert(str(CAMINHO_MODELO))
    riscos = [prever_risco_bert(texto, modelo, tokenizer) for texto in teste_x]
    previsto = [1 if risco >= LIMIAR_RISCO else 0 for risco in riscos]

    print("=== Relatório de classificação (BERTimbau) ===")
    print(classification_report(teste_y, previsto, target_names=["legítima", "desinformação"]))

    f1_bert = f1_score(teste_y, previsto, average="macro")
    print(f"F1 macro BERTimbau: {f1_bert:.3f}")
    print(f"F1 macro baseline TF-IDF (docs/canva.md): {F1_BASELINE:.3f}\n")

    if f1_bert > F1_BASELINE:
        print(
            "BERTimbau superou o baseline — critério de entrada da Task 10 satisfeito. "
            f"Modelo salvo em {CAMINHO_MODELO}."
        )
    else:
        print(
            "BERTimbau NÃO superou o baseline TF-IDF no conjunto de teste. Pelo critério "
            "da Task 10, o ganho não justifica o custo de inferência — o baseline "
            "continua sendo o classificador de produção."
        )


if __name__ == "__main__":
    main()

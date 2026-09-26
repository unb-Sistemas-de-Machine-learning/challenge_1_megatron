"""Treina o baseline no recorte de saúde e reporta as métricas.

Uso: python scripts/treina_modelo.py
"""

import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.classificador import prever_risco, salvar, treinar

CAMINHO_DADOS = RAIZ / "dados" / "processed" / "saude_ptbr.csv"
CAMINHO_MODELO = RAIZ / "modelos" / "baseline.joblib"


def main() -> None:
    # Colunas geradas pela Task 5 (ver dados/README.md). rotulo: 1 = desinformação.
    df = pd.read_csv(CAMINHO_DADOS, dtype={"id_par": str})
    print(f"Notícias: {len(df)}")
    print(df["rotulo"].value_counts(), "\n")

    # A divisão é por par: a falsa e a verdadeira de um mesmo assunto ficam
    # sempre do mesmo lado. Separá-las vazaria o assunto entre treino e teste.
    divisor = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    indices_treino, indices_teste = next(divisor.split(df, groups=df["id_par"]))
    treino, teste = df.iloc[indices_treino], df.iloc[indices_teste]
    treino_x, treino_y = treino["texto"].tolist(), treino["rotulo"].tolist()
    teste_x, teste_y = teste["texto"].tolist(), teste["rotulo"].tolist()

    modelo = treinar(treino_x, treino_y)
    previsto = modelo.predict(teste_x)

    print("=== Relatório de classificação ===")
    print(classification_report(teste_y, previsto, target_names=["legítima", "desinformação"]))
    print("=== Matriz de confusão ===")
    print(confusion_matrix(teste_y, previsto))

    salvar(modelo, CAMINHO_MODELO)
    print(f"\nModelo salvo em {CAMINHO_MODELO}")


if __name__ == "__main__":
    main()

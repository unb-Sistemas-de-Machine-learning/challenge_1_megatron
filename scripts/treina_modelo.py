"""Treina o baseline no recorte de saúde e reporta as métricas.

Uso: python scripts/treina_modelo.py
"""

import sys
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.classificador import prever_risco, salvar, treinar

CAMINHO_DADOS = RAIZ / "dados" / "processed" / "saude_ptbr.csv"
CAMINHO_DADOS_FAKERECOGNA = RAIZ / "dados" / "processed" / "saude_fakerecogna.csv"
CAMINHO_MODELO = RAIZ / "modelos" / "baseline.joblib"

TreinarFn = Callable[[list[str], list[int]], object]
MetricaFn = Callable[[object, list[str], list[int]], float]


def avaliar_cross_source(
    df: pd.DataFrame, treinar_fn: TreinarFn, metrica_fn: MetricaFn
) -> dict[str, float | None]:
    """Mede o viés de fonte: treina numa fonte, testa na outra.

    Um modelo que aprendeu o estilo editorial do portal (em vez de sinais de
    desinformação) terá F1 alto na mesma fonte e baixo na fonte oposta. Exige
    as duas fontes presentes em `df["fonte"]`; se faltar uma, devolve None nas
    duas direções em vez de comparar parcialmente.
    """
    fontes = set(df["fonte"].unique())
    if not {"fakebr", "fakerecogna"} <= fontes:
        return {"fakebr_para_fakerecogna": None, "fakerecogna_para_fakebr": None}

    fakebr = df[df["fonte"] == "fakebr"]
    fakerecogna = df[df["fonte"] == "fakerecogna"]

    modelo_fakebr = treinar_fn(fakebr["texto"].tolist(), fakebr["rotulo"].tolist())
    f1_fakebr_para_fakerecogna = metrica_fn(
        modelo_fakebr, fakerecogna["texto"].tolist(), fakerecogna["rotulo"].tolist()
    )

    modelo_fakerecogna = treinar_fn(fakerecogna["texto"].tolist(), fakerecogna["rotulo"].tolist())
    f1_fakerecogna_para_fakebr = metrica_fn(
        modelo_fakerecogna, fakebr["texto"].tolist(), fakebr["rotulo"].tolist()
    )

    return {
        "fakebr_para_fakerecogna": f1_fakebr_para_fakerecogna,
        "fakerecogna_para_fakebr": f1_fakerecogna_para_fakebr,
    }


def _f1_macro(modelo, textos, rotulos) -> float:
    previsto = modelo.predict(textos)
    return f1_score(rotulos, previsto, average="macro")


def main() -> None:
    # Colunas geradas pela Task 5 (ver dados/README.md). rotulo: 1 = desinformação.
    df = pd.read_csv(CAMINHO_DADOS, dtype={"id_par": str})
    df["fonte"] = "fakebr"
    print(f"Notícias (Fake.br): {len(df)}")
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

    f1_same_source = f1_score(teste_y, previsto, average="macro")
    print(f"F1 macro (same-source): {f1_same_source:.3f}\n")

    cross_source = {"fakebr_para_fakerecogna": None, "fakerecogna_para_fakebr": None}
    if CAMINHO_DADOS_FAKERECOGNA.exists():
        df_fakerecogna = pd.read_csv(CAMINHO_DADOS_FAKERECOGNA, dtype={"id_par": str})
        df_combinado = pd.concat([df, df_fakerecogna], ignore_index=True)
        cross_source = avaliar_cross_source(df_combinado, treinar, _f1_macro)
        print("=== Avaliação cross-source (viés de fonte) ===")
        print(f"Treina Fake.br -> testa FakeRecogna: {cross_source['fakebr_para_fakerecogna']}")
        print(f"Treina FakeRecogna -> testa Fake.br: {cross_source['fakerecogna_para_fakebr']}\n")
    else:
        print(
            f"Aviso: {CAMINHO_DADOS_FAKERECOGNA} não encontrado — avaliação cross-source "
            "pulada. Rode scripts/prepara_fakerecogna.py para habilitá-la.\n"
        )

    salvar(modelo, CAMINHO_MODELO)
    print(f"Modelo salvo em {CAMINHO_MODELO}")


if __name__ == "__main__":
    main()

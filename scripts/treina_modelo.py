"""Treina o baseline no recorte de saúde e reporta as métricas.

Uso: python scripts/treina_modelo.py
"""

import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from prepara_dataset import IMPRESSAO_DIGITAL_FAKEBR
from verdade_ou_fake.classificador import prever_risco, salvar, treinar
from verdade_ou_fake.model_card import calcular_hash_artefato, montar_card, salvar_card

CAMINHO_DADOS = RAIZ / "dados" / "processed" / "saude_ptbr.csv"
CAMINHO_DADOS_FAKERECOGNA = RAIZ / "dados" / "processed" / "saude_fakerecogna.csv"
CAMINHO_MODELO = RAIZ / "modelos" / "baseline.joblib"
CAMINHO_CARD = RAIZ / "modelos" / "cards" / "baseline.json"


def _commit_atual() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=RAIZ, text=True
        ).strip()
    except subprocess.CalledProcessError:
        return "desconhecido"


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

    card = montar_card(
        nome="baseline",
        tipo="tfidf_logreg",
        commit=_commit_atual(),
        dados={
            # Hardcoded: `treinar()` acima só é chamado com dados do Fake.br.
            # `df_combinado`/FakeRecogna entram apenas na avaliação cross-source
            # (diagnóstico de viés de fonte), nunca no treino em si — então a
            # existência do CSV do FakeRecogna não deve mudar o que este card
            # declara como fonte de treino. Treino combinado é um reforço
            # futuro deliberadamente fora do escopo desta correção.
            "fontes": ["fakebr"],
            "hash_fakebr": IMPRESSAO_DIGITAL_FAKEBR,
            # FakeRecogna: o hash do parquet varia a cada download e não é
            # persistido entre scripts hoje (prepara_fakerecogna.py calcula o
            # seu próprio hash, mas só imprime — não grava em lugar algum que
            # este script possa ler). Encanar essa passagem de metadata entre
            # scripts é um reforço futuro, não feito aqui para manter esta
            # correção enxuta.
            "hash_fakerecogna": None,
            "volume_treino": len(treino_x),
            "volume_teste": len(teste_x),
        },
        metricas={
            "f1_macro_same_source": f1_same_source,
            "f1_macro_cross_source_fakebr_para_fakerecogna": cross_source["fakebr_para_fakerecogna"],
            "f1_macro_cross_source_fakerecogna_para_fakebr": cross_source["fakerecogna_para_fakebr"],
        },
        limiar_aprovacao={"f1_macro_same_source_minimo": 0.75, "queda_maxima_cross_source": 0.20},
        artefato_hash=calcular_hash_artefato(CAMINHO_MODELO),
        treinado_em=datetime.now().astimezone().isoformat(),
        treinado_por="scripts/treina_modelo.py",
    )
    salvar_card(card, CAMINHO_CARD)
    print(f"Model card salvo em {CAMINHO_CARD}")


if __name__ == "__main__":
    main()

"""Etapa [1] — classificador de risco textual (baseline).

TF-IDF + Regressão Logística. Este é o baseline do projeto: qualquer modelo
mais complexo (BERTimbau, Fase 2) precisa superá-lo para justificar o custo.

Limitação essencial: este modelo aprende ESTILO de escrita, não FATOS. Ele
erra em alegações falsas bem redigidas. A Camada 2 existe para cobrir isso.
"""

from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


def construir_modelo() -> Pipeline:
    """Monta o pipeline TF-IDF + Regressão Logística ainda não treinado.

    ngram_range=(1, 2) captura bigramas como "cura milagrosa", que isolados
    ("cura", "milagrosa") diriam menos.
    """
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=1,
                    max_features=50_000,
                    sublinear_tf=True,
                ),
            ),
            (
                "classificador",
                LogisticRegression(max_iter=1000, class_weight="balanced"),
            ),
        ]
    )


def treinar(textos: list[str], rotulos: list[int]) -> Pipeline:
    """Treina o modelo. Rótulo 1 = desinformação, 0 = legítima."""
    modelo = construir_modelo()
    modelo.fit(textos, rotulos)
    return modelo


def salvar(modelo: Pipeline, caminho: Path) -> None:
    """Serializa o modelo treinado em disco."""
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, caminho)


def carregar(caminho: Path) -> Pipeline:
    """Carrega um modelo salvo por `salvar`."""
    return joblib.load(caminho)


def prever_risco(modelo: Pipeline, texto: str) -> float:
    """Devolve a probabilidade de o texto ser desinformação, entre 0 e 1."""
    return float(modelo.predict_proba([texto])[0][1])

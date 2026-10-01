"""Etapa [1] — classificador de risco textual (baseline).

TF-IDF + Regressão Logística. Este é o baseline do projeto: qualquer modelo
mais complexo (BERTimbau, Fase 2) precisa superá-lo para justificar o custo.

Limitação essencial: este modelo aprende ESTILO de escrita, não FATOS. Ele
erra em alegações falsas bem redigidas. A Camada 2 existe para cobrir isso.
"""

from pathlib import Path

import joblib
import numpy as np
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.utils.class_weight import compute_class_weight
from transformers import (
    BertForSequenceClassification,
    BertTokenizer,
    PreTrainedModel,
    PreTrainedTokenizer,
    Trainer,
    TrainingArguments,
)


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


# Task 10 (Fase 2): fine-tuning do BERTimbau. Só substitui o baseline acima se
# superar o F1 macro do TF-IDF no conjunto de teste — ver scripts/treina_bert.py.
MODELO_BERT_PADRAO = "neuralmind/bert-base-portuguese-cased"
TAMANHO_MAXIMO_TOKENS = 512


def construir_modelo_bert(
    checkpoint: str = MODELO_BERT_PADRAO,
    camadas_congeladas: int = 0,
) -> tuple[PreTrainedModel, PreTrainedTokenizer]:
    """Carrega o BERTimbau (ou outro checkpoint compatível) para classificação binária.

    `camadas_congeladas` congela os embeddings e as primeiras N camadas do
    encoder (contadas a partir da entrada). Isso reduz a memória do
    otimizador — o Adam guarda duas cópias extras por parâmetro treinável —
    o que importa neste projeto porque o fine-tuning roda em CPU sem GPU
    dedicada e com poucos GB de RAM livres.
    """
    tokenizer = BertTokenizer.from_pretrained(checkpoint)
    modelo = BertForSequenceClassification.from_pretrained(checkpoint, num_labels=2)

    if camadas_congeladas > 0:
        for parametro in modelo.bert.embeddings.parameters():
            parametro.requires_grad = False
        for camada in modelo.bert.encoder.layer[:camadas_congeladas]:
            for parametro in camada.parameters():
                parametro.requires_grad = False

    return modelo, tokenizer


def prever_risco_bert(
    texto: str,
    modelo: PreTrainedModel,
    tokenizer: PreTrainedTokenizer,
    tamanho_maximo_tokens: int = TAMANHO_MAXIMO_TOKENS,
) -> float:
    """Devolve a probabilidade de o texto ser desinformação segundo o BERTimbau."""
    modelo.eval()
    entradas = tokenizer(
        texto, return_tensors="pt", truncation=True, max_length=tamanho_maximo_tokens
    )
    with torch.no_grad():
        saida = modelo(**entradas)
    probabilidades = torch.softmax(saida.logits, dim=-1)
    return float(probabilidades[0][1])


class _ConjuntoDeTextos(torch.utils.data.Dataset):
    """Pré-tokeniza textos+rótulos uma vez para alimentar o `Trainer` do HF."""

    def __init__(
        self,
        textos: list[str],
        rotulos: list[int],
        tokenizer: PreTrainedTokenizer,
        tamanho_maximo_tokens: int = TAMANHO_MAXIMO_TOKENS,
    ):
        self._codificacoes = tokenizer(
            textos,
            truncation=True,
            max_length=tamanho_maximo_tokens,
            padding=True,
        )
        self._rotulos = rotulos

    def __len__(self) -> int:
        return len(self._rotulos)

    def __getitem__(self, indice: int) -> dict:
        item = {chave: torch.tensor(valor[indice]) for chave, valor in self._codificacoes.items()}
        item["labels"] = torch.tensor(self._rotulos[indice])
        return item


class _TreinadorComPesoDeClasse(Trainer):
    """`Trainer` que pondera a perda pela frequência de cada classe.

    Mesma razão do `class_weight="balanced"` do baseline TF-IDF: sem isso, um
    corpus desbalanceado empurra o modelo a sempre prever a classe majoritária.
    """

    def __init__(self, *args, pesos_classe: torch.Tensor | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pesos_classe = pesos_classe

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        rotulos = inputs.pop("labels")
        saida = model(**inputs)
        perda = torch.nn.functional.cross_entropy(saida.logits, rotulos, weight=self.pesos_classe)
        return (perda, saida) if return_outputs else perda


def treinar_bert(
    textos: list[str],
    rotulos: list[int],
    caminho_saida: Path,
    checkpoint: str = MODELO_BERT_PADRAO,
    epocas: int = 3,
    tamanho_lote: int = 8,
    camadas_congeladas: int = 0,
    tamanho_maximo_tokens: int = TAMANHO_MAXIMO_TOKENS,
) -> None:
    """Faz o fine-tuning do BERTimbau e salva modelo+tokenizer em `caminho_saida`.

    `tamanho_lote` pequeno por padrão — este projeto roda em CPU sem GPU
    dedicada, e lotes grandes de sequências longas esgotam a memória
    disponível. `camadas_congeladas` e `tamanho_maximo_tokens` existem pela
    mesma razão — ver `construir_modelo_bert`.
    """
    modelo, tokenizer = construir_modelo_bert(checkpoint, camadas_congeladas=camadas_congeladas)
    conjunto = _ConjuntoDeTextos(textos, rotulos, tokenizer, tamanho_maximo_tokens)

    pesos_classe = torch.tensor(
        compute_class_weight("balanced", classes=np.array([0, 1]), y=rotulos), dtype=torch.float
    )

    argumentos = TrainingArguments(
        output_dir=str(Path(caminho_saida) / "_checkpoints"),
        num_train_epochs=epocas,
        per_device_train_batch_size=tamanho_lote,
        logging_strategy="epoch",
        report_to=[],
        save_strategy="no",
    )

    treinador = _TreinadorComPesoDeClasse(
        model=modelo,
        args=argumentos,
        train_dataset=conjunto,
        pesos_classe=pesos_classe,
    )
    treinador.train()
    print(f"Histórico de treino: {treinador.state.log_history}")

    caminho_saida = Path(caminho_saida)
    caminho_saida.mkdir(parents=True, exist_ok=True)
    modelo.save_pretrained(caminho_saida)
    tokenizer.save_pretrained(caminho_saida)

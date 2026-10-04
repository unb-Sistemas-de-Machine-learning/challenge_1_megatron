"""Fine-tuning da etapa [2c] (Task 12, Fase 2 — condicional).

A Task 11 previu isso como condicional: só valeria a pena fazer fine-tuning
"se a Task 11 for avaliada em 50-100 pares anotados manualmente e ficar com
acurácia abaixo de 0,75". `scripts/avalia_suporte.py` mediu 48,1% de acurácia
nos 79 pares de `dados/avaliacao/suporte_pubmed.json` — bem abaixo do limiar,
então esse módulo existe.

Duas diferenças deliberadas em relação ao plano original:

1. **Sem MedNLI.** O plano previa pré-treinar com o MedNLI (PhysioNet) antes
   dos pares PT-BR. O MedNLI exige credenciamento individual no PhysioNet que
   não está disponível neste ambiente — o fine-tuning aqui parte direto do
   checkpoint zero-shot (que já é uma NLI multilíngue) para os pares PT-BR.
2. **Só a cabeça de classificação é treinada.** O checkpoint de produção
   (mDeBERTa-v3-base) tem 279M parâmetros; o conjunto anotado disponível tem
   79 pares, não os ~500 previstos no plano. Fazer fine-tuning completo do
   backbone com tão pouco dado arrisca overfit severo e não cabe na memória
   deste ambiente (sem GPU, poucos GB de RAM livre). Treinar só a cabeça
   (linear probing) é a escolha apropriada para essa quantidade de dado e tem
   custo de memória desprezível — o resultado deve ser lido como exploratório,
   não como o fine-tuning completo de produção que o plano original imaginava.
"""

from pathlib import Path

import torch
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    PreTrainedModel,
    PreTrainedTokenizer,
    Trainer,
    TrainingArguments,
)

from verdade_ou_fake.suporte import MODELO_NLI

TAMANHO_MAXIMO_TOKENS = 512

# Mesma ordem de rótulos do checkpoint XNLI: entailment=0, neutral=1, contradiction=2.
ROTULO_PARA_ID = {"apoia": 0, "nao_determinado": 1, "contradiz": 2}


def construir_modelo_treinavel(
    checkpoint: str = MODELO_NLI,
) -> tuple[PreTrainedModel, PreTrainedTokenizer]:
    """Carrega o modelo de NLI com o backbone congelado — só a cabeça de classificação treina.

    Ver o motivo no docstring do módulo: 79 pares não sustentam fine-tuning
    completo de um backbone de 279M parâmetros sem overfit severo. O `pooler`
    fica congelado também: é uma camada linear sem não-linearidade (sem
    ativação limitante), e treiná-la nesta escala de dado explode — perda
    saltando de ~4 para ~80 entre uma época e outra com `grad_norm=0`, sinal
    de pesos saturados/degenerados. Só `classifier` (768→3) é treinável.
    """
    tokenizer = AutoTokenizer.from_pretrained(checkpoint)
    modelo = AutoModelForSequenceClassification.from_pretrained(
        checkpoint, num_labels=3, ignore_mismatched_sizes=True
    )

    for parametro in modelo.parameters():
        parametro.requires_grad = False
    for nome, modulo in modelo.named_children():
        if nome == "classifier":
            for parametro in modulo.parameters():
                parametro.requires_grad = True

    return modelo, tokenizer


class _ConjuntoDePares(Dataset):
    """Pré-tokeniza pares (premissa=resumo, hipótese=alegação, rótulo)."""

    def __init__(
        self, pares: list[tuple[str, str, str]], tokenizer: PreTrainedTokenizer
    ):
        premissas = [premissa for premissa, _, _ in pares]
        hipoteses = [hipotese for _, hipotese, _ in pares]
        self._codificacoes = tokenizer(
            premissas,
            hipoteses,
            truncation=True,
            max_length=TAMANHO_MAXIMO_TOKENS,
            padding=True,
        )
        self._rotulos = [ROTULO_PARA_ID[rotulo] for _, _, rotulo in pares]

    def __len__(self) -> int:
        return len(self._rotulos)

    def __getitem__(self, indice: int) -> dict:
        item = {chave: torch.tensor(valor[indice]) for chave, valor in self._codificacoes.items()}
        item["labels"] = torch.tensor(self._rotulos[indice])
        return item


def treinar_suporte(
    pares: list[tuple[str, str, str]],
    caminho_saida: Path,
    checkpoint: str = MODELO_NLI,
    epocas: int = 3,
    tamanho_lote: int = 4,
    taxa_aprendizado: float = 5e-4,
) -> None:
    """Continua o treino do modelo de NLI nos pares PT-BR (resumo, alegação, rótulo).

    `rotulo` é "apoia" | "contradiz" | "nao_determinado" — mesmo vocabulário de
    `classificar_suporte`. Internamente mapeado para entailment/contradiction/neutral.

    `taxa_aprendizado` maior que o padrão do `Trainer` (5e-5) porque só a
    camada `classifier` (768→3, ~2,3 mil parâmetros) está treinável — taxas
    pensadas para fine-tuning completo de um backbone de 279M parâmetros
    convergem devagar demais para uma cabeça desse tamanho.
    """
    modelo, tokenizer = construir_modelo_treinavel(checkpoint)
    conjunto = _ConjuntoDePares(pares, tokenizer)

    passos_totais = epocas * max(1, len(conjunto) // tamanho_lote)
    argumentos = TrainingArguments(
        output_dir=str(Path(caminho_saida) / "_checkpoints"),
        num_train_epochs=epocas,
        per_device_train_batch_size=tamanho_lote,
        learning_rate=taxa_aprendizado,
        warmup_steps=max(1, passos_totais // 10),
        weight_decay=0.01,
        logging_strategy="epoch",
        report_to=[],
        save_strategy="no",
    )

    treinador = Trainer(model=modelo, args=argumentos, train_dataset=conjunto)
    resultado = treinador.train()
    print(f"Histórico de treino: {treinador.state.log_history}")

    caminho_saida = Path(caminho_saida)
    caminho_saida.mkdir(parents=True, exist_ok=True)
    modelo.save_pretrained(caminho_saida)
    tokenizer.save_pretrained(caminho_saida)

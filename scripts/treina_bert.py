"""Faz o fine-tuning do BERTimbau no recorte de saúde e compara com o baseline.

Usa a MESMA divisão treino/teste de `scripts/treina_modelo.py` (mesmo
`random_state`, mesmo agrupamento por par) para que a comparação de F1 seja
justa. Por critério da Task 10: o BERTimbau só substitui o baseline TF-IDF se
superar o F1 macro dele no conjunto de teste — ganho marginal não justifica o
custo de inferência de um modelo muito maior.

Gera `modelos/cards/bertimbau.json` (status `staging`) com o F1, o hash dos
pesos e o limiar do gate. O app só serve o modelo depois que uma pessoa revisa
o card e o promove manualmente a `producao`.

Uso:
    python scripts/treina_bert.py                    # treina, avalia e gera o card
    python scripts/treina_bert.py --somente-avaliar  # reavalia o modelo já salvo e regenera o card
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import GroupShuffleSplit

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from prepara_dataset import IMPRESSAO_DIGITAL_FAKEBR
from treina_modelo import _commit_atual
from verdade_ou_fake.classificador import construir_modelo_bert, prever_risco_bert, treinar_bert
from verdade_ou_fake.model_card import calcular_hash_artefato, montar_card, salvar_card
from verdade_ou_fake.modelo_producao import ARQUIVO_PESOS

CAMINHO_DADOS = RAIZ / "dados" / "processed" / "saude_ptbr.csv"
CAMINHO_MODELO = RAIZ / "modelos" / "bertimbau"
CAMINHO_CARD = RAIZ / "modelos" / "cards" / "bertimbau.json"
LIMIAR_RISCO = 0.5
TAMANHO_MAXIMO_TOKENS = 256  # o app usa o mesmo truncamento na inferência

# F1 macro do baseline TF-IDF, registrado em docs/canva.md (validação cruzada
# por par, 10 dobras): 0,80 ± 0,08.
F1_BASELINE = 0.80


def main(somente_avaliar: bool = False) -> None:
    df = pd.read_csv(CAMINHO_DADOS, dtype={"id_par": str})
    print(f"Notícias: {len(df)}")
    print(df["rotulo"].value_counts(), "\n")

    divisor = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    indices_treino, indices_teste = next(divisor.split(df, groups=df["id_par"]))
    treino, teste = df.iloc[indices_treino], df.iloc[indices_teste]
    treino_x, treino_y = treino["texto"].tolist(), treino["rotulo"].tolist()
    teste_x, teste_y = teste["texto"].tolist(), teste["rotulo"].tolist()

    print(f"Treino: {len(treino_x)} · Teste: {len(teste_x)}\n")
    if somente_avaliar:
        print(f"Pulando o treino: reavaliando o modelo já salvo em {CAMINHO_MODELO}.\n")
    else:
        _treinar(treino_x, treino_y)

    modelo, tokenizer = construir_modelo_bert(str(CAMINHO_MODELO))
    riscos = [
        prever_risco_bert(texto, modelo, tokenizer, TAMANHO_MAXIMO_TOKENS) for texto in teste_x
    ]
    previsto = [1 if risco >= LIMIAR_RISCO else 0 for risco in riscos]

    print("=== Relatório de classificação (BERTimbau) ===")
    print(classification_report(teste_y, previsto, target_names=["legítima", "desinformação"]))

    f1_bert = f1_score(teste_y, previsto, average="macro")
    print(f"F1 macro BERTimbau: {f1_bert:.3f}")
    print(f"F1 macro baseline TF-IDF (docs/canva.md): {F1_BASELINE:.3f}\n")

    if f1_bert > F1_BASELINE:
        print("BERTimbau superou o baseline — critério de entrada da Task 10 satisfeito.")
    else:
        print(
            "BERTimbau NÃO superou o baseline TF-IDF no conjunto de teste. Pelo critério "
            "da Task 10, o ganho não justifica o custo de inferência — não promova este card."
        )

    card = montar_card(
        nome="bertimbau",
        tipo="bert_finetuned",
        commit=_commit_atual(),
        dados={
            "fontes": ["fakebr"],
            "hash_fakebr": IMPRESSAO_DIGITAL_FAKEBR,
            "hash_fakerecogna": None,
            "volume_treino": len(treino_x),
            "volume_teste": len(teste_x),
        },
        metricas={
            "f1_macro_same_source": f1_bert,
            # Avaliar cross-source exigiria dois fine-tunings extras (horas em
            # CPU); o gate só avalia essa condição quando o valor existe.
            "f1_macro_cross_source_fakebr_para_fakerecogna": None,
            "f1_macro_cross_source_fakerecogna_para_fakebr": None,
        },
        limiar_aprovacao={"f1_macro_same_source_minimo": 0.75, "queda_maxima_cross_source": 0.20},
        artefato_hash=calcular_hash_artefato(CAMINHO_MODELO / ARQUIVO_PESOS),
        treinado_em=datetime.now().astimezone().isoformat(),
        treinado_por="scripts/treina_bert.py",
    )
    salvar_card(card, CAMINHO_CARD)
    print(
        f"Modelo em {CAMINHO_MODELO}; model card salvo em {CAMINHO_CARD} (status: staging). "
        "Rode scripts/verifica_gate.py e, se aprovado, promova o card a 'producao' manualmente."
    )


def _treinar(treino_x: list[str], treino_y: list[int]) -> None:
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
        tamanho_maximo_tokens=TAMANHO_MAXIMO_TOKENS,
    )


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument(
        "--somente-avaliar",
        action="store_true",
        help="não treina; reavalia o modelo já salvo e regenera o model card",
    )
    main(argumentos.parse_args().somente_avaliar)

"""Testa a plumbing do fine-tuning da etapa [2c] (Task 12, Fase 2 — condicional).

A Task 11 mediu 40,5% de acurácia do zero-shot nos 79 pares anotados em
`dados/avaliacao/suporte_pubmed.json` — abaixo do limiar de 75% do plano, o
que aciona o critério de entrada da Task 12. Como no resto do projeto, os
testes usam um checkpoint de NLI minúsculo para exercitar a integração sem
pagar o custo do modelo de produção (mDeBERTa-v3-base, 279M parâmetros) a
cada rodada — o fine-tuning real acontece em `scripts/treina_suporte.py`.
"""

from pathlib import Path

from verdade_ou_fake.suporte_treino import construir_modelo_treinavel, treinar_suporte

CHECKPOINT_DE_TESTE = "hf-internal-testing/tiny-random-DebertaV2ForSequenceClassification"

PARES = [
    ("A trial found significant reduction in symptoms with the drug.", "o remédio trata a doença", "apoia"),
    ("No significant difference was found versus placebo.", "o remédio trata a doença", "contradiz"),
    ("This review discusses general background on the topic.", "o remédio trata a doença", "nao_determinado"),
    ("The treatment group showed clear clinical improvement.", "o remédio trata a doença", "apoia"),
]


def test_construir_modelo_treinavel_congela_o_backbone():
    modelo, tokenizer = construir_modelo_treinavel(checkpoint=CHECKPOINT_DE_TESTE)

    parametros_treinaveis = [nome for nome, p in modelo.named_parameters() if p.requires_grad]
    assert parametros_treinaveis, "deveria haver ao menos os parâmetros da cabeça de classificação treináveis"
    assert all("classifier" in nome for nome in parametros_treinaveis)


def test_treinar_suporte_salva_um_modelo_utilizavel(tmp_path: Path):
    caminho_saida = tmp_path / "suporte_teste"

    treinar_suporte(PARES, caminho_saida, checkpoint=CHECKPOINT_DE_TESTE, epocas=1)

    assert (caminho_saida / "config.json").exists()

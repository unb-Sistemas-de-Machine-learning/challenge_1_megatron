"""Testa a plumbing do classificador BERTimbau (Task 10, Fase 2).

Usa um checkpoint minúsculo (`hf-internal-testing/tiny-random-BertForSequenceClassification`)
em vez do BERTimbau real (`neuralmind/bert-base-portuguese-cased`, ~440MB) — mesmo
padrão que os testes já usam para o PubMed e o NLI: exercitar a integração real
com a biblioteca sem pagar o custo do modelo de produção em cada rodada de teste.
A avaliação com o BERTimbau real acontece em `scripts/treina_bert.py`, fora da
suíte automatizada, do mesmo jeito que `scripts/treina_modelo.py` avalia o baseline.

ATENÇÃO — única exceção à regra "testes sem rede" (docs/plano-implementacao.md):
o checkpoint minúsculo ainda é baixado do Hugging Face Hub na primeira chamada de
`from_pretrained`. Diferente do PubMed e do NLI (que usam fixture local), aqui não
há como evitar a rede sem vendorizar o checkpoint no repositório. Marcados com
`@pytest.mark.rede` para que `pytest -m "not rede"` rode a suíte inteira offline.
"""

from pathlib import Path

import pytest

from verdade_ou_fake.classificador import construir_modelo_bert, prever_risco_bert, treinar_bert

CHECKPOINT_DE_TESTE = "hf-internal-testing/tiny-random-BertForSequenceClassification"

pytestmark = pytest.mark.rede

TEXTOS = [
    "URGENTE!!! Cura milagrosa escondida pelos médicos, compartilhe agora",
    "MILAGRE! Remédio secreto elimina a doença em 3 dias sem efeito colateral",
    "Estudo publicado avalia a eficácia do tratamento em ensaio clínico controlado",
    "Pesquisa universitária analisa o uso do medicamento em pacientes internados",
]
ROTULOS = [1, 1, 0, 0]


def test_construir_modelo_bert_devolve_modelo_com_duas_classes():
    modelo, tokenizer = construir_modelo_bert(checkpoint=CHECKPOINT_DE_TESTE)

    assert modelo.config.num_labels == 2
    assert tokenizer("teste", return_tensors="pt") is not None


def test_construir_modelo_bert_congela_as_primeiras_camadas_do_encoder():
    modelo, _ = construir_modelo_bert(checkpoint=CHECKPOINT_DE_TESTE, camadas_congeladas=1)

    assert not any(p.requires_grad for p in modelo.bert.embeddings.parameters())
    assert not any(p.requires_grad for p in modelo.bert.encoder.layer[0].parameters())
    assert any(p.requires_grad for p in modelo.classifier.parameters())


def test_risco_bert_fica_entre_zero_e_um():
    modelo, tokenizer = construir_modelo_bert(checkpoint=CHECKPOINT_DE_TESTE)

    risco = prever_risco_bert("Qualquer texto de notícia", modelo, tokenizer)

    assert 0.0 <= risco <= 1.0


def test_treinar_bert_salva_um_modelo_utilizavel(tmp_path: Path):
    caminho_saida = tmp_path / "bertimbau_teste"

    treinar_bert(
        TEXTOS, ROTULOS, caminho_saida, checkpoint=CHECKPOINT_DE_TESTE, epocas=1
    )

    modelo, tokenizer = construir_modelo_bert(checkpoint=str(caminho_saida))
    risco = prever_risco_bert(TEXTOS[0], modelo, tokenizer)

    assert 0.0 <= risco <= 1.0
    assert (caminho_saida / "config.json").exists()

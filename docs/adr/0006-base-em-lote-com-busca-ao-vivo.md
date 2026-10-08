# ADR 0006 — Base pré-ingerida em lote com ampliação ao vivo sob demanda

## Contexto

A versão anterior consultava o PubMed ao vivo a cada pergunta, com limite de 3
requisições por segundo, e isso pesava na latência. Por outro lado, uma base fixa não
cobre alegações fora do que foi ingerido.

## Decisão

Dois caminhos.

**Principal: ingestão em lote** (`scripts/ingere_pubmed.py`). Para cada medicamento e
cada par medicamento × condição do vocabulário, busca revisões sistemáticas,
meta-análises e ensaios randomizados, excluindo estudos só em animais. O resultado é
`dados/base/pubmed.jsonl`, versionado no git (1.069 resumos na versão atual), com
`manifesto.json` (data, volume, SHA-256). O workflow `ingestao-base.yml` repete a
ingestão toda semana. O banco é derivado do JSONL por `scripts/constroi_base.py`.

**Secundário: busca ao vivo.** Quando a base local devolve menos de 2 fontes para a
alegação, o sistema consulta o PubMed na hora, indexa os artigos achados (origem
`ao_vivo`) e refaz a busca. Dá para desligar com `VOF_BUSCA_AO_VIVO=0`.

## Alternativas consideradas

- **Só ao vivo.** Era o desenho anterior: lento e dependente do PubMed a cada pergunta.
- **Só em lote.** Rápido, mas cobre apenas o vocabulário. Uma alegação fora dele
  terminaria em "não foi possível verificar" mesmo havendo literatura.
- **Corpus muito maior, sem vocabulário.** Volume e custo de embeddings incompatíveis
  com uma máquina pequena, sem GPU, e com a escala do projeto.

## Consequências

- Perguntas dentro do vocabulário não esperam pelo PubMed.
- A base é versionada: cada resposta se liga à versão que a gerou pelo hash do
  manifesto, que também entra na chave de cache.
- Alegações novas enriquecem a base. No deploy atual o banco fica num volume persistente,
  então esses artigos permanecem entre reinícios. Eles não entram no JSONL versionado:
  só passam a fazer parte da base reproduzível se a ingestão semanal os alcançar (por
  ampliação do vocabulário).
- A cobertura em lote é restrita ao vocabulário (23 medicamentos e 15 condições).
- O JSONL cresce no git a cada atualização. Nesta escala é aceitável.

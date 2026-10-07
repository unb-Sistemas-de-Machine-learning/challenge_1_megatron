# ADR 0001 — Trocar o pipeline de classificador + NLI por RAG com LLM de terceiros

## Contexto

A versão anterior combinava um classificador de estilo (BERTimbau), um dicionário de 38
termos para achar o par medicamento + condição, a busca ao vivo no PubMed e um modelo
NLI mDeBERTa zero-shot em CPU. Na prática: respostas em dezenas de segundos, cobertura
limitada aos 38 termos, NLI impreciso em texto biomédico, e um classificador que mede
o estilo do portal, não o fato. A história completa está em
[Arquitetura](../arquitetura.md#o-que-mudou-e-por-que).

## Decisão

Adotar RAG. Uma base de resumos do PubMed é indexada antes (embeddings + índice
lexical). Na consulta, o sistema recupera os estudos mais próximos da alegação e um LLM
de terceiros, acessado por API, redige o veredito usando apenas essas fontes numeradas.
O código confere a saída (ver [ADR 0007](0007-guardas-deterministicas.md)).

## Alternativas consideradas

- **Manter o pipeline e consertá-lo.** O fine-tuning do NLI exigiria dados anotados que
  não tínhamos (o experimento anterior usou 79 pares). Também não resolvia a lentidão
  nem a cobertura.
- **LLM sem recuperação.** Responderia de memória, sem fontes verificáveis, com risco
  alto de inventar estudos. Contraria a GQ5.
- **LLM local pequeno.** Roda no `docker compose` via Ollama e fica como plano B, mas
  em CPU tende a ser lento e menos capaz do que os modelos hospedados.

## Consequências

- Cobertura de alegações além de um dicionário, com texto legível e citações.
- Dependência de um serviço de terceiros e da cota gratuita dele. Mitigada por fallback
  entre modelos, modo degradado e troca de provedor
  ([ADR 0004](0004-cliente-openai-compativel-groq.md)).
- O LLM pode errar mesmo com as guardas. É uma limitação declarada.
- Resultados não reprodutíveis bit a bit: o provedor pode mudar o modelo.
- Perdemos a restrição "nenhum componente depende de serviço externo" do desenho
  anterior.

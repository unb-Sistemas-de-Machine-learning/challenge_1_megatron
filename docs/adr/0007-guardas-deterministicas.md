# ADR 0007 — Guardas determinísticas sobre a saída do LLM

## Contexto

LLMs inventam citações, afirmam com mais confiança do que os dados permitem e
desobedecem instruções. Em saúde, uma resposta confiante e errada é o pior caso (GQ5).
Pedir no prompt para "não inventar" ajuda, mas não garante.

## Decisão

Conferir a saída por código, sem depender do modelo:

1. **Citação obrigatória.** O prompt exige `[n]` em toda frase factual. O
   `FiltroDeCitacoes` remove, durante o streaming, qualquer `[n]` que não esteja na
   lista de fontes entregue ao modelo.
2. **Rebaixamento.** Se o veredito é afirmativo (`APOIADA`, `CONTESTADA`, `EXAGERADA`) e
   nenhuma citação válida sobrou, vira `INCONCLUSIVA` com confiança baixa e um aviso.
3. **Teto de confiança pelo tipo de estudo.** A confiança não passa do que as fontes
   citadas sustentam: `alta` exige ao menos uma revisão sistemática ou meta-análise
   citada; se a mais forte é um ensaio randomizado, o teto é `media`; senão, `baixa`.
4. **Vereditos que o LLM não decide.** `NAO_VERIFICAVEL` (nenhuma fonte encontrada) e
   `FORA_DO_ESCOPO` (assunto fora de saúde) saem do código, com texto fixo. O primeiro
   diz que ausência de estudo não prova que a alegação é falsa.

Cabeçalho fora do formato vira `INCONCLUSIVA` com confiança baixa.

## Alternativas consideradas

- **Confiar no prompt.** Barato, sem garantia.
- **Segundo LLM como verificador.** Dobra a cota gasta e herda o mesmo tipo de erro.
- **Verificar cada frase contra a fonte por NLI.** É o desenho que abandonamos pela
  imprecisão e pela lentidão.

## Consequências

- Citações inexistentes e afirmações sem fonte são barradas por construção.
- As guardas **não** verificam se a citação sustenta a frase. O modelo pode citar uma
  fonte real e interpretá-la mal. Por isso a interface sempre mostra as fontes, com link.
- A confiança reflete o tipo de estudo, não a direção nem a qualidade metodológica do
  resultado.
- Regras simples são fáceis de testar offline, sem LLM.

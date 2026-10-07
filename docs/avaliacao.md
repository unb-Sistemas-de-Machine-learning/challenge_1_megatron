# Avaliação

Como o sistema é medido, o que já foi medido e o que ainda falta medir.

## Como medir

`scripts/avalia_rag.py` roda o fluxo completo sobre `dados/avaliacao/alegacoes.json`, um
conjunto de 20 alegações com gabarito escrito pela equipe. Cada caso lista os vereditos
aceitáveis, porque em várias alegações mais de uma leitura é defensável (por exemplo,
"contestada" ou "exagerada"). O script usa um banco temporário, então o cache não
interfere.

```bash
python scripts/avalia_rag.py            # os 20 casos
python scripts/avalia_rag.py --limite 8 # subconjunto
```

O resultado vai para `dados/avaliacao/resultado_rag.json`, com o modelo usado e o hash
da base, e traz quatro medidas:

| Medida | O que responde |
|---|---|
| Acurácia do veredito | O veredito ficou entre os aceitáveis do gabarito? |
| Afirmativos com citação válida | Todo veredito afirmativo cita ao menos uma fonte que existe? |
| Casos com fontes | A recuperação encontrou estudos para a alegação? |
| Latência (mediana, p95, primeiro texto) | A resposta é rápida o bastante para o usuário esperar? |

## O que foi medido em 07/10/2026

### Sistema sem o LLM

Medido na máquina de desenvolvimento (8 núcleos, sem GPU), com a base de 1.069 resumos.

| Etapa | Tempo |
|---|---|
| Busca híbrida na base | cerca de 10 ms por consulta |
| Fluxo completo com um LLM simulado de resposta imediata | 83 ms |
| Construção do banco a partir do JSONL | 72 s |
| Inicialização do contêiner até `/api/saude` responder | poucos segundos |

A imagem Docker tem 671 MB e o serviço usa cerca de 630 MB de RAM em repouso.

O tempo que o usuário espera é, portanto, quase todo do provedor de LLM: duas chamadas
por consulta, uma curta para identificar a alegação e uma em streaming para redigir.

### Fluxo completo com LLM local pequeno

Sem chave de provedor disponível no dia, o fluxo foi exercitado com `qwen2.5:3b` no
Ollama, em CPU, nos 8 primeiros casos do conjunto.

| Medida | Resultado |
|---|---|
| Acurácia do veredito | 5 de 8 |
| Afirmativos com citação válida | 4 de 4 |
| Casos com fontes | 8 de 8 |
| Latência mediana | 70 s |

Os três erros:

| Alegação | Obtido | Esperado |
|---|---|---|
| Ivermectina cura covid-19 | Apoiada, confiança alta | Contestada ou inconclusiva |
| Azitromicina é eficaz contra a covid-19 | Inconclusiva | Contestada |
| Metformina ajuda a controlar a glicose no diabetes tipo 2 | Inconclusiva | Apoiada |

O que esse teste mostra:

- A recuperação funcionou em todos os casos, e nenhuma citação inválida chegou ao usuário.
- Um modelo de 3 bilhões de parâmetros **não serve para redigir o veredito**. No caso
  da ivermectina ele recebeu meta-análises que não mostram benefício e concluiu o
  contrário, citando as próprias fontes. As guardas de código não pegam esse erro:
  elas conferem se a citação existe, não se a fonte diz o que o texto afirma.
- LLM local em CPU é inviável para uso interativo. Serve só como plano de contingência.

### O que falta medir

**Os números com os modelos de produção (Groq) não foram medidos.** Com a chave
configurada, rode `python scripts/avalia_rag.py` e substitua a seção acima pelos
resultados. Enquanto isso não for feito, a qualidade do veredito em produção é uma
hipótese, não um resultado.

Também não foram medidos: a compreensão da resposta por pessoas leigas (GQ3), a taxa de
extração limpa de texto nos portais de notícia brasileiros (GQ8) e o efeito do sistema
na decisão do usuário, que é o objetivo de negócio.

## Limitações do método

- O conjunto tem 20 casos e foi escrito pela própria equipe, com alegações escolhidas
  entre os temas que a base cobre. Ele detecta regressões, mas não estima o desempenho
  em alegações reais colhidas de redes sociais.
- O gabarito aceita mais de um veredito por caso, o que infla a acurácia.
- "Citação válida" mede se a fonte citada existe, não se ela sustenta a frase. Medir
  fidelidade exige leitura humana ou um segundo modelo como juiz.

## Testes automatizados

`pytest -m "not rede"` roda a suíte offline. Ela cobre o banco, a recuperação, o
cliente de LLM com transporte simulado, o orquestrador do RAG com LLM falso (cache,
guardas, busca ampliada, modo degradado) e a API.

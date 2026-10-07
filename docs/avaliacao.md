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

### Fluxo completo com os modelos de produção (Groq)

Os 20 casos, com `openai/gpt-oss-120b` na redação e `openai/gpt-oss-20b` na
identificação da alegação, `reasoning_effort` baixo, e 12 s de pausa entre casos para
respeitar o limite de tokens por minuto.

| Medida | Resultado |
|---|---|
| Acurácia do veredito | 20 de 20 |
| Afirmativos com citação válida | 17 de 17 |
| Casos com fontes | 18 de 20 (os outros dois são o caso sem literatura e o fora de escopo, como esperado) |
| Latência mediana | 1,5 s |
| Latência p95 | 3,8 s |
| Respostas degradadas | 0 |

Distribuição dos vereditos: 7 apoiadas, 5 contestadas, 5 exageradas, 1 inconclusiva,
1 não verificável e 1 fora do escopo.

**Como ler esse 20 de 20.** A primeira rodada deu 19 de 20, e a rodada anterior a ela
classificou "Ivermectina cura covid-19" como "exagera", quando o mais preciso é
"contradiz". Depois disso a definição dos vereditos no prompt foi ajustada e um defeito
na detecção de texto fora de escopo foi corrigido, e a rodada foi repetida. O número
final foi obtido, portanto, **num conjunto que serviu de guia para os ajustes**. Ele
mostra que o sistema não tem erro grosseiro nos temas que a base cobre. Não é uma
estimativa de acerto em alegações novas.

### Rajada de consultas novas

Oito alegações fora do conjunto, enviadas em sequência sem pausa, pela API:

- Todas responderam, entre 1,1 s e 2,9 s.
- Cinco foram redigidas pelo `gpt-oss-120b`. Quando o limite de tokens por minuto dele
  estourou, duas passaram para o `qwen3.8-27b` e uma para o `gpt-oss-20b`, sem erro
  para o usuário.
- Em uma delas o modelo reserva não citou fonte, e a guarda rebaixou o veredito para
  "evidência insuficiente", com aviso.
- Em duas a confiança foi limitada por só haver estudo isolado entre as fontes citadas.

Um link real (o verbete da Wikipédia sobre ivermectina) foi lido, analisado e
respondido em 2,8 s, com o download da página incluído.

### Fluxo completo com LLM local pequeno

Antes de haver chave do Groq, o fluxo foi exercitado com `qwen2.5:3b` no Ollama, em
CPU, nos 8 primeiros casos: 5 de 8 corretos, com mediana de 70 s por resposta. No caso
da ivermectina o modelo recebeu meta-análises que não mostram benefício e concluiu o
contrário, citando as próprias fontes. Duas lições ficaram:

- Um modelo de 3 bilhões de parâmetros não serve para redigir o veredito, e as guardas
  de código não pegam esse erro: elas conferem se a citação existe, não se a fonte diz
  o que o texto afirma.
- LLM local em CPU é inviável para uso interativo. Serve só como plano de contingência.

### O que falta medir

- Acerto em alegações reais colhidas de redes sociais, com gabarito feito por alguém de
  fora da equipe.
- Fidelidade: se cada frase da explicação é sustentada pela fonte que ela cita.
- Qualidade das respostas quando o fallback cai nos modelos menores.
- Compreensão da resposta por pessoas leigas (GQ3), taxa de extração limpa nos portais
  de notícia brasileiros (GQ8) e o efeito na decisão do usuário, que é o objetivo de
  negócio.

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

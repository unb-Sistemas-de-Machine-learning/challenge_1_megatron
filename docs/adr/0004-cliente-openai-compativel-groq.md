# ADR 0004 — Cliente compatível com OpenAI, Groq como padrão, fallback entre modelos

## Contexto

O sistema precisa de um LLM para identificar a alegação e redigir o veredito, com custo
zero para a demo. Planos gratuitos têm cota, e uma cota estourada derruba a demo.

Limites do Groq no plano gratuito, **na data da consulta (07/10/2026) e sujeitos a
mudança**: 30 requisições por minuto; por dia, cerca de 100 mil tokens no
`llama-3.3-70b-versatile`, 200 mil no `openai/gpt-oss-120b` e 500 mil no
`llama-3.1-8b-instant`. O Gemini tem modelos Flash no plano gratuito, com limites por
projeto exibidos no AI Studio.

## Decisão

Escrever um cliente HTTP mínimo (`llm.py`, só `httpx`) para a API de chat compatível com
a da OpenAI, com streaming. Provedor, chave e modelos vêm de variáveis de ambiente
(`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODELOS`, `LLM_MODELO_RAPIDO`). O padrão é o Groq.

`LLM_MODELOS` é uma lista tentada em ordem. Se um modelo responde com erro de cota
(429) ou de servidor, o próximo assume, desde que nenhum texto tenha sido entregue ao
usuário ainda. Somar as cotas dos três modelos é o que sustenta a demo. Um modelo
pequeno (`LLM_MODELO_RAPIDO`) cuida da etapa curta de identificar a alegação.

## Alternativas consideradas

- **Gemini como padrão.** Funciona trocando as variáveis (há endpoint compatível). O
  Groq foi preferido por dar acesso a três modelos com cotas separadas na mesma conta.
- **Ollama local.** Sem cota e sem dependência externa. Em CPU tende a ser lento, então
  fica como plano B (`docker compose` com o perfil `local-llm`).
- **SDK de um provedor só.** Prende o código a um fornecedor. A API é simples o bastante
  para dispensar o SDK.

## Consequências

- Trocar de provedor é trocar variáveis, sem mexer no código.
- Se todos os modelos falham, o sistema cai no modo degradado (fontes sem veredito).
- Os prompts foram escritos para o formato de saída dos modelos padrão. Outro modelo
  pode seguir pior o formato; nesse caso o interpretador do cabeçalho devolve
  `INCONCLUSIVA` com confiança baixa em vez de falhar.
- Os limites gratuitos mudam sem aviso. Todo número sobre cota deve ser lido com sua data.

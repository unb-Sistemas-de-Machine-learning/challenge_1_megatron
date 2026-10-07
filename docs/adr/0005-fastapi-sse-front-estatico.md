# ADR 0005 — FastAPI com SSE e front estático em vez de Streamlit

## Contexto

O Streamlit serviu à primeira versão, mas a resposta nova tem várias etapas e texto
gerado aos poucos. O usuário precisa ver o progresso e o texto chegando, em vez de
esperar tudo. Também queremos endpoints próprios para feedback, saúde e métricas.

## Decisão

Servir o sistema com FastAPI. `POST /api/analisar` responde com Server-Sent Events: um
fluxo de eventos JSON (etapas, alegação, fontes, veredito, texto, fim). O front é um
único `web/index.html`, estático e sem etapa de build, servido pelo próprio FastAPI. Há
limite de requisições por cliente. Contrato em [API](../api.md).

## Alternativas consideradas

- **Continuar no Streamlit.** Dá pouco controle sobre streaming e sobre a estrutura de
  endpoints, e não expõe uma API que outros clientes possam usar.
- **WebSocket.** É bidirecional, mas aqui a comunicação é de uma via por consulta. SSE é
  mais simples.
- **Front com framework (React, Vue).** Exigiria etapa de build e mais dependências para
  uma tela só.

## Consequências

- O progresso e o texto aparecem conforme são produzidos.
- Um front sem build é fácil de revisar e servir, mas tem menos estrutura para crescer.
- O navegador só faz SSE com `GET` pelo `EventSource`; como a entrada pode ser grande,
  o front lê o corpo da resposta de um `POST` por `fetch`.
- O proxy à frente do app não pode bufferizar a resposta. A API envia
  `X-Accel-Buffering: no` para pedir isso.

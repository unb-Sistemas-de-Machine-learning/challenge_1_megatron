# ADR 0008 — Hugging Face Spaces (Docker) para hospedagem gratuita

## Contexto

A versão anterior era servida por um túnel temporário do Cloudflare a partir de um
notebook do Colab: o link mudava a cada execução e a demo morria com a sessão.
Precisamos de uma URL estável e gratuita que rode um contêiner Python com ONNX e SQLite.

## Decisão

Publicar num Hugging Face Space com SDK Docker, no plano gratuito de CPU (2 vCPU, 16 GB
de RAM). O deploy é feito por `scripts/publica_space.py`, chamado pelo workflow
`deploy-app.yml`. O Dockerfile constrói o banco na etapa de build e sobe o uvicorn na
porta 7860.

## Alternativas consideradas

- **Render.** Alternativa avaliada. Preferimos o Space pela folga de 16 GB de RAM para o
  modelo de embeddings e a matriz de vetores.
- **Koyeb com 512 MB de RAM.** Pouca memória para o modelo ONNX, a matriz de embeddings
  e o processo web juntos.
- **Máquina própria com túnel.** É o que já tínhamos: depende de um computador ligado e
  de um link que muda. Continua como plano B de demonstração, com `docker compose`.

## Consequências

- URL estável e deploy automatizado pelo GitHub Actions.
- O Space **hiberna após inatividade** e acorda no próximo acesso, então o primeiro
  acesso depois de uma pausa é mais lento.
- **O disco do plano gratuito não é persistente.** A cada reinício, o registro de
  consultas, o cache de páginas e os artigos vindos da busca ao vivo se perdem. A base
  de conhecimento não: é reconstruída na imagem. O monitoramento (`/api/metricas`) só
  enxerga o período desde o último reinício.
- Persistência de verdade exigiria um volume pago ou um banco externo, que deixamos de
  fora por ora.
- Limites e condições do plano gratuito são do provedor e podem mudar.

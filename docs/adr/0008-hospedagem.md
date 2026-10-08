# 0008 Hospedagem: de Hugging Face Spaces para VM no Azure

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

## Revisão em 07/10/2026

A premissa desta decisão caiu. Em 07/10/2026 a criação do Space foi recusada pelo Hugging Face: Spaces com Docker no hardware `cpu-basic` passaram a exigir assinatura PRO (9 dólares por mês na data da consulta). O caminho abaixo só vale com essa assinatura. Sem ela, a imagem roda em qualquer host de contêiner com pelo menos 1 GB de RAM: o `Dockerfile` lê a porta de `PORT` e o serviço só precisa de `LLM_API_KEY`.

## Decisão revista em 07/10/2026

Hospedar numa **máquina virtual do Azure**, com o crédito do Azure for Students, que não
pede cartão. A VM roda dois contêineres: o serviço e um proxy Caddy, que cuida do HTTPS.
A publicação é feita por `scripts/publica_azure.sh`.

Alternativas consideradas nesta revisão:

- **Hugging Face PRO.** Manteria o desenho original, por 9 dólares mensais, e
  continuaria sem disco persistente.
- **Render gratuito.** 512 MB de RAM, menos do que o serviço precisa, e hiberna após 15
  minutos.
- **Northflank gratuito.** 1 GB de RAM segundo a documentação consultada; não testado.
- **Máquina da equipe com túnel.** Custo zero e endereço fixo com Tailscale Funnel, mas
  depende de um computador pessoal ligado.

Consequências:

- Endereço fixo com HTTPS e disco persistente: o registro de consultas e o feedback
  deixam de zerar a cada reinício, o que o Space gratuito não oferecia.
- O serviço fica no ar sem depender de máquina pessoal e não hiberna.
- Custo real, descontado do crédito: cerca de 10 dólares por mês só de VM.
- A região Brazil South não é permitida na assinatura de estudante; a VM está em Chile
  Central.
- Operar uma VM é responsabilidade da equipe: atualizações do sistema, monitoramento
  do disco e da memória, que é justa (1 GB).
- O deploy deixou de ser automático a cada push. É um comando manual, com a CLI do
  Azure autenticada.

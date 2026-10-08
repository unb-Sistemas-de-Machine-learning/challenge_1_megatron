# Operação

Como subir, configurar, publicar, atualizar e acompanhar o sistema.

## Subir localmente

Com Python 3.11:

```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # e preencha LLM_API_KEY (chave gratuita em console.groq.com)
python scripts/constroi_base.py
PYTHONPATH=src uvicorn verdade_ou_fake.api:app --port 7860
```

`scripts/constroi_base.py` lê `dados/base/pubmed.jsonl`, calcula os embeddings e grava o
banco em `dados/vof.db` (cerca de 70 s em CPU para a base atual). Se você pular esse
passo, o serviço indexa a base sozinho na subida, quando o banco está vazio, em segundo
plano. Abra <http://localhost:7860>.

Com Docker:

```bash
docker compose up --build
```

O Dockerfile constrói o banco na etapa de build e sobe o uvicorn na porta 7860.

Testes:

```bash
pip install -r requirements-dev.txt --extra-index-url https://download.pytorch.org/whl/cpu
pytest -m "not rede"
```

`-m "not rede"` exclui os testes que tocam a rede. É o que o `ci.yml` roda.

## Variáveis de ambiente

A fonte da verdade é `src/verdade_ou_fake/config.py`. Sem `LLM_API_KEY` o serviço sobe em
modo degradado: recupera e mostra as fontes, mas não redige o veredito.

| Variável | Padrão | Para quê |
|---|---|---|
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Endereço da API de chat compatível com OpenAI |
| `LLM_API_KEY` | vazio | Chave do provedor. Se vazia, usa `GROQ_API_KEY`; se ambas vazias, modo degradado |
| `LLM_MODELOS` | `openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b` | Lista separada por vírgulas, tentada em ordem (fallback em erro de cota ou de servidor) |
| `LLM_MODELO_RAPIDO` | `openai/gpt-oss-20b` | Modelo pequeno que identifica a alegação |
| `LLM_ESFORCO_RACIOCINIO` | `low` | Enviado como `reasoning_effort`; deixe vazio para provedores que não aceitam o parâmetro |
| `LLM_TIMEOUT` | `45` | Segundos de espera pela resposta do LLM antes de tentar o próximo modelo |
| `VOF_BANCO` | `dados/vof.db` | Caminho do arquivo SQLite |
| `VOF_MODELO_EMBEDDING` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Modelo de embeddings (trocar exige reconstruir o banco) |
| `VOF_SIMILARIDADE_MINIMA` | `0.45` | Cosseno mínimo para uma fonte contar como relevante; abaixo disso a base local é considerada sem cobertura |
| `VOF_CACHE_HORAS` | `168` | Validade do cache de respostas |
| `VOF_LIMITE_POR_MINUTO` | `12` | Requisições por minuto por cliente em `/api/analisar` |
| `VOF_BUSCA_AO_VIVO` | `1` | `0` desliga a busca ampliada no PubMed |
| `VOF_PLANILHA_CSV` | vazio | Link CSV da planilha de temas em alta, publicada na web |
| `VOF_DESTAQUES_AUTOMATICOS` | `1` | `0` desliga os temas tirados do Google Notícias |
| `VOF_DESTAQUES_MAXIMO` | `6` | Temas por rodada |
| `VOF_DESTAQUES_HORAS` | `6` | Intervalo entre rodadas |
| `VOF_DESTAQUES_PAUSA` | `25` | Segundos entre um tema e outro, para caber no limite do LLM |
| `VOF_SINAL_ESTILO` | `0` | `1` liga o sinal de estilo do BERTimbau; desligado por padrão porque marca texto legítimo como arriscado |
| `VOF_MODELO_RISCO` | `modelos/bertimbau` (se existir) | Pasta ou id no Hub dos pesos do BERTimbau (sinal de estilo, opcional) |
| `VOF_MODELO_RISCO_REVISAO` | vazio | Commit do repositório do modelo no Hub, para fixar a versão |
| `NCBI_API_KEY` | vazio | Chave gratuita do NCBI: sobe o limite do PubMed de 3 para 10 requisições por segundo |
| `NCBI_EMAIL` | vazio | E-mail de contato, pedido pelo NCBI |

Constantes que não são variáveis: 5 fontes por resposta (`fontes_por_resposta`) e 15
candidatos por busca.

## Trocar de provedor de LLM

Trocar o provedor é mudar variáveis, sem tocar no código. Mude **também** os nomes de
modelo: `LLM_MODELOS` e `LLM_MODELO_RAPIDO` trazem nomes do Groq por padrão e outro
provedor não os reconhece.

| Provedor | `LLM_BASE_URL` | `LLM_API_KEY` |
|---|---|---|
| Groq (padrão) | `https://api.groq.com/openai/v1` | chave de console.groq.com |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | chave do AI Studio |
| Ollama (local) | `http://localhost:11434/v1` | `ollama` (qualquer valor não vazio) |

Limites dos planos gratuitos, **na data da consulta (07/10/2026), sujeitos a mudança**:

- Groq: os três modelos de chat disponíveis (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b` e `openai/gpt-oss-20b`) têm, cada um, 8.000 tokens por minuto e 1.000 requisições por dia, lidos dos cabeçalhos de resposta da API. Uma consulta gasta cerca de 2.500 tokens, então cada modelo aguenta umas três consultas novas por minuto; a lista com fallback soma os três.
- Gemini: modelos Flash no plano gratuito, com limites por projeto exibidos no AI Studio.

Confira `GET /api/saude` depois de trocar: `llm` deve ser `true` e `modelos` deve listar
os novos.

## Publicar no Azure

O app roda numa máquina virtual do Azure, com o crédito do Azure for Students
([ADR 0008](adr/0008-hospedagem.md)). Endereço atual: <https://verdade-ou-fake-megatron.chilecentral.cloudapp.azure.com>

1. **Conta.** Ative o Azure for Students com o e-mail institucional em
   <https://azure.microsoft.com/free/students>. Não pede cartão.
2. **CLI.** Instale a CLI do Azure e rode `az login --use-device-code`.
3. **Chave do LLM.** Tenha o `.env` na raiz, com `LLM_API_KEY`. O script copia esse
   arquivo para a VM, sem comentários e com permissão restrita.
4. **Publicar.**

   ```bash
   ROTULO=verdade-ou-fake-megatron LOCAL=chilecentral TAMANHO=Standard_B2ats_v2 scripts/publica_azure.sh
   ```

   O script cria o grupo de recursos e a VM (Ubuntu 22.04, Docker instalado por
   `deploy/cloud-init.yml`, 2 GB de swap), abre as portas 80 e 443, constrói a imagem
   localmente, envia por SSH e sobe `deploy/docker-compose.yml`. Ele gera a chave
   `~/.ssh/vof_azure` na primeira vez. Rodar de novo publica uma versão nova na mesma VM.
5. **Conferir.** Abra o endereço e consulte `/api/saude`: `documentos` deve ser o total
   da base e `llm` deve ser `true`.

| Variável do script | Padrão | Observação |
|---|---|---|
| `ROTULO` | obrigatória | Prefixo do endereço: `<ROTULO>.<LOCAL>.cloudapp.azure.com` |
| `LOCAL` | `brazilsouth` | A assinatura de estudante da UnB só aceitou `chilecentral`, `mexicocentral`, `eastus`, `canadacentral` e `northcentralus` |
| `TAMANHO` | `Standard_B1s` | Em `chilecentral` os tamanhos pequenos disponíveis eram `Standard_B2ats_v2` e `Standard_B2ts_v2` |
| `GRUPO`, `VM` | `verdade-ou-fake`, `vof` | Nomes do grupo de recursos e da máquina |

**O que persiste.** O banco fica no volume `banco`, no disco da VM. Consultas, feedback,
cache e artigos da busca ampliada sobrevivem a reinícios e a novas publicações. Uma
publicação com base nova não substitui o banco do volume: os documentos novos entram na
próxima ingestão ou busca; para reconstruir do zero, apague o volume na VM.

**Custo.** A VM `Standard_B2ats_v2` (2 vCPU, 1 GB de RAM) custava 0,0132 dólar por hora
em `chilecentral` em 07/10/2026, cerca de 9,60 dólares por mês, mais disco e IP público.
O crédito de estudante é de 100 dólares por ano. Para parar de gastar:
`az vm deallocate -g verdade-ou-fake -n vof`; para apagar tudo:
`az group delete -n verdade-ou-fake`.

**Memória.** O serviço usa cerca de 380 MB logo após subir numa máquina de 1 GB, com
parte do sistema em swap. Funciona, mas sem folga.

**Acesso à VM.** `ssh -i ~/.ssh/vof_azure vof@<endereço>`; os contêineres ficam em
`~/servico` (`docker compose logs -f app`).

## Temas em alta

A seção "Em alta nesta semana" da página inicial vem de duas fontes
([ADR 0010](adr/0010-temas-em-alta.md)): uma planilha da equipe e as manchetes de saúde
do Google Notícias.

**Planilha.** Crie um Google Sheets com a coluna `alegacao` (uma alegação por linha) e,
se quiser, a coluna `data` no formato `dd/mm/aaaa`; linhas com mais de 7 dias saem
sozinhas. Em *Arquivo, Compartilhar, Publicar na web*, escolha a aba e o formato CSV, e
coloque o link em `VOF_PLANILHA_CSV`. A planilha publicada é pública para leitura.

**Rodada.** O serviço atualiza os temas um minuto depois de subir e a cada
`VOF_DESTAQUES_HORAS`. Para forçar: `python scripts/atualiza_destaques.py`; na VM,
`cd ~/servico && docker compose exec app python scripts/atualiza_destaques.py`.

Cada tema passa por busca no PubMed, que alimenta a base, e pela checagem completa, que
fica no cache. Temas da planilha aparecem sempre. Temas automáticos só aparecem com
veredito afirmativo de confiança alta, então a seção pode ficar vazia sem planilha.

## Atualizar a base

O workflow `ingestao-base.yml` roda a ingestão do PubMed toda semana e commita a base
atualizada (`dados/base/pubmed.jsonl` e `manifesto.json`). Um novo commit na `main` leva
a uma nova imagem, e o banco é reconstruído no build.

À mão:

```bash
python scripts/ingere_pubmed.py              # reescreve o JSONL e o manifesto
python scripts/constroi_base.py              # indexa no banco local
```

`constroi_base.py` só acrescenta documentos que ainda não estão no banco. Para
reconstruir do zero, apague `dados/vof.db` (ou o arquivo de `VOF_BANCO`) antes.

Para ampliar o que a ingestão cobre, acrescente linhas a `dados/vocabulario_seed.csv`
(`termo_pt,termo_en,tipo`, com tipo `medicamento` ou `condicao`) e rode a ingestão. Cada
novo medicamento gera uma consulta por condição.

Uma base nova muda o `sha256` do manifesto e, com ele, a chave de cache: respostas
antigas não são reaproveitadas.

## O que olhar em `/api/metricas`

Formato do retorno em [API](api.md#get-apimetricas). O banco fica num volume
persistente da VM, então os números acumulam entre reinícios e publicações.

| Sinal | O que indica | O que fazer |
|---|---|---|
| `latencia_ms_p50` e `latencia_ms_p95` | Tempo das respostas geradas (sem cache) | P95 muito acima de P50 aponta para fallback entre modelos, busca ao vivo ou cota perto do limite. Veja `/api/saude` e os logs |
| `vereditos` | Proporção de cada código | Muitos `NAO_VERIFICAVEL` e `INCONCLUSIVA` indicam lacuna de cobertura: ampliar o vocabulário. Muitos `FORA_DO_ESCOPO` indicam que os usuários colam o que o sistema não trata |
| `com_busca_ao_vivo` | Consultas em que a base local não bastou | Cada uma é uma lacuna candidata. Veja as alegações em `consultas.alegacao` e decida se entram no vocabulário |
| `citacoes_validas_media` | Quantas citações válidas por resposta | Queda sugere que o modelo (ou o prompt) está seguindo pior o formato; revise `LLM_MODELOS` |
| `feedback_positivo` e `feedback_negativo` | Opinião dos usuários | Leia as respostas com feedback negativo (`consultas.eventos`) e classifique: fonte errada, texto errado, veredito errado |
| `respondidas_do_cache` | Peso do cache | Mostra quanta cota de LLM o cache poupa |
| `documentos_por_origem` | Quantos documentos vieram do lote e quantos da busca ao vivo | Documentos `ao_vivo` mostram o que o uso trouxe além do lote |

As tabelas citadas (`consultas`, com `alegacao`, `fontes`, `eventos` e `feedback`) não têm
endpoint: só se lê o texto delas no arquivo SQLite (`sqlite3 dados/vof.db`), localmente ou
onde houver acesso ao contêiner.

**Ciclo de feedback.** O que as métricas mostram só vira melhoria se alguém agir. O
caminho é: ler as consultas com feedback negativo e as com busca ao vivo; separar o erro
de cobertura (falta estudo na base: ampliar o vocabulário), de recuperação (o estudo
existe e não veio: ajustar `VOF_SIMILARIDADE_MINIMA` ou a busca) e de redação (o estudo
veio e o texto errou: revisar o prompt ou o modelo); corrigir; e conferir de novo nas
métricas. Esse ciclo é manual.

## Plano B para a demo

Se o provedor de LLM cair, estourar a cota ou a VM estiver indisponível, rode tudo
numa máquina local com Ollama:

```bash
docker compose --profile local-llm up --build
```

O perfil `local-llm` sobe o Ollama junto com o app. Baixe antes um modelo com
`ollama pull <modelo>` e aponte o app para ele: `LLM_BASE_URL` para o endereço do
Ollama, `LLM_API_KEY=ollama`, e `LLM_MODELOS` e `LLM_MODELO_RAPIDO` com o nome do modelo
baixado. Os valores exatos para o `docker compose` estão em `.env.example` e
`docker-compose.yml`.

Um modelo local em CPU é mais lento do que o Groq. Teste antes. E mesmo sem nenhum LLM, o
sistema continua mostrando as fontes recuperadas em modo degradado.

Preparação para a apresentação: faça uma consulta de teste pouco antes e confira
`/api/saude`. A VM não hiberna.

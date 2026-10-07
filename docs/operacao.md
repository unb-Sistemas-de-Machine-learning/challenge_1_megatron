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
| `LLM_MODELOS` | `llama-3.3-70b-versatile,openai/gpt-oss-120b,llama-3.1-8b-instant` | Lista separada por vírgulas, tentada em ordem (fallback em erro de cota ou de servidor) |
| `LLM_MODELO_RAPIDO` | `llama-3.1-8b-instant` | Modelo pequeno que identifica a alegação |
| `LLM_TIMEOUT` | `45` | Segundos de espera pela resposta do LLM antes de tentar o próximo modelo |
| `VOF_BANCO` | `dados/vof.db` | Caminho do arquivo SQLite |
| `VOF_MODELO_EMBEDDING` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Modelo de embeddings (trocar exige reconstruir o banco) |
| `VOF_SIMILARIDADE_MINIMA` | `0.45` | Cosseno mínimo para uma fonte contar como relevante; abaixo disso a base local é considerada sem cobertura |
| `VOF_CACHE_HORAS` | `168` | Validade do cache de respostas |
| `VOF_LIMITE_POR_MINUTO` | `12` | Requisições por minuto por cliente em `/api/analisar` |
| `VOF_BUSCA_AO_VIVO` | `1` | `0` desliga a busca ampliada no PubMed |
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

- Groq: 30 requisições por minuto; por dia, cerca de 100 mil tokens no
  `llama-3.3-70b-versatile`, 200 mil no `openai/gpt-oss-120b` e 500 mil no
  `llama-3.1-8b-instant`. É por isso que a lista de modelos com fallback soma as cotas.
- Gemini: modelos Flash no plano gratuito, com limites por projeto exibidos no AI Studio.

Confira `GET /api/saude` depois de trocar: `llm` deve ser `true` e `modelos` deve listar
os novos.

## Publicar no Hugging Face Space

O app roda num Space com SDK Docker, no plano gratuito de CPU (2 vCPU, 16 GB de RAM). O
Space hiberna após inatividade e acorda no próximo acesso. O disco não é persistente: o
registro de consultas zera a cada reinício, e a base de conhecimento é reconstruída na
imagem ([ADR 0008](adr/0008-hugging-face-spaces.md)).

1. **Criar o Space.** Em huggingface.co, *New Space*, SDK **Docker**, hardware CPU
   gratuito. Anote o id, no formato `usuario/nome-do-space`.
2. **Configurar o segredo do LLM.** No Space, *Settings, Variables and secrets*: crie o
   **secret** `LLM_API_KEY` com a chave do provedor. Se quiser, crie também `NCBI_API_KEY`
   (secret) e `NCBI_EMAIL` (variável). Outras variáveis da tabela acima entram como
   variáveis do Space.
3. **Configurar o GitHub.** No repositório, *Settings, Secrets and variables, Actions*:
   - variável `HF_SPACE` com o id do Space;
   - secret `HF_TOKEN` com um token do Hugging Face com permissão de escrita.
4. **Publicar.** O workflow `deploy-app.yml` roda a cada push na `main` (e sob demanda,
   pelo *Run workflow*): executa os testes offline e chama `scripts/publica_space.py`.
   Enquanto `HF_SPACE` não existe, o job é pulado.
   Para publicar à mão: `python scripts/publica_space.py usuario/nome-do-space`, depois de
   `hf auth login` ou com `HF_TOKEN` no ambiente.
5. **Conferir.** Quando o build do Space terminar, abra a URL e consulte
   `/api/saude`: `documentos` deve ser o total da base e `llm` deve ser `true`.

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

Formato do retorno em [API](api.md#get-apimetricas). Como o banco do Space zera a cada
reinício, os números valem para o período desde a última subida.

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

Se o provedor de LLM cair, estourar a cota ou o Space estiver indisponível, rode tudo
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

Preparação para a apresentação: acorde o Space e faça uma consulta de teste pouco antes,
porque o primeiro acesso depois de hibernar é lento; confira `/api/saude`.

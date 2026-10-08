# API

FastAPI, definida em `src/verdade_ou_fake/api.py`. O front estático (`web/index.html`) é
servido na raiz (`/`) e usa estes mesmos endpoints. Com o servidor rodando, a
documentação interativa gerada pelo FastAPI fica em `/docs`.

| Método e caminho | Para quê |
|---|---|
| `POST /api/analisar` | Analisa uma alegação; resposta em Server-Sent Events |
| `POST /api/feedback` | Registra se a resposta ajudou |
| `GET /api/saude` | Estado do serviço e versão da base |
| `GET /api/metricas` | Indicadores de operação |

## `POST /api/analisar`

Corpo JSON:

```json
{ "entrada": "link de notícia ou texto colado" }
```

`entrada` tem de 8 a 20.000 caracteres (fora disso, a API responde 422). Se a entrada
inteira é uma URL `http(s)`, o sistema extrai o texto da página; senão, trata como texto.

A resposta tem `Content-Type: text/event-stream`. Cada evento é uma linha
`data: <JSON>` seguida de linha em branco. O campo `tipo` diz de que evento se trata.

```bash
curl -N -X POST http://localhost:7860/api/analisar \
  -H 'Content-Type: application/json' \
  -d '{"entrada": "Ivermectina cura a covid-19, diz corrente de WhatsApp"}'
```

(`-N` desliga o buffer do curl, para ver os eventos chegando.)

### Eventos

| `tipo` | Campos | Quando |
|---|---|---|
| `etapa` | `texto` | Progresso: "Lendo a notícia" (só links), "Identificando a alegação", "Buscando estudos na base científica", "Ampliando a busca no PubMed" (só se a base local não cobre), "Redigindo a análise" |
| `alegacao` | `texto`, `titulo_noticia` | Alegação identificada. `titulo_noticia` é o título da página, ou `null` se a entrada era texto |
| `estilo` | `risco` | Sinal de estilo do BERTimbau: probabilidade, de 0 a 1 (3 casas), de o texto ser desinformação segundo o classificador. Só aparece se o modelo está carregado e respondeu em até 4 s |
| `fontes` | `fontes` | Lista de fontes (abaixo). Pode ser vazia. Não é enviado quando o veredito é `FORA_DO_ESCOPO` |
| `veredito` | `codigo`, `rotulo`, `confianca`, `resumo` | Veredito. Pode chegar uma segunda vez, se as guardas mudaram o veredito ou a confiança: vale o último |
| `texto` | `texto` | Pedaço do texto da análise, em ordem. Concatene os pedaços |
| `fim` | `latencia_ms`, `modelo`, `do_cache`, `citadas`, `aviso`, `consulta_id` | Último evento de uma análise bem-sucedida |
| `erro` | `mensagem` | Falha. Encerra o fluxo, sem evento `fim` |

Cada item de `fontes`:

| Campo | Conteúdo |
|---|---|
| `n` | Número usado nas citações `[n]` do texto |
| `titulo`, `url`, `ano` | Dados do artigo; a URL aponta para o PubMed |
| `tipos` | Tipos de publicação do PubMed (por exemplo, `Systematic Review`) |
| `forca` | `forte` (revisão sistemática ou meta-análise), `moderada` (ensaio randomizado) ou `fraca` |
| `origem` | `PubMed` |

Valores de `codigo` (`ROTULOS` em `rag.py`):

| `codigo` | `rotulo` | Quem decide |
|---|---|---|
| `APOIADA` | Tem respaldo científico | LLM, sujeito às guardas |
| `CONTESTADA` | A ciência contradiz | LLM, sujeito às guardas |
| `EXAGERADA` | Há base, mas a alegação exagera | LLM, sujeito às guardas |
| `INCONCLUSIVA` | Evidência insuficiente ou conflitante | LLM, guardas, ou modo degradado |
| `NAO_VERIFICAVEL` | Não foi possível verificar | Código, quando nenhuma fonte foi encontrada |
| `FORA_DO_ESCOPO` | Fora do escopo | Código, quando o texto não é alegação de saúde |

`confianca` é `alta`, `media` ou `baixa`.

Campos de `fim`:

- `latencia_ms`: tempo total da análise.
- `modelo`: modelo de LLM que redigiu o texto, ou `null` quando nenhum texto foi gerado
  (ou nenhuma citação válida sobrou).
- `do_cache`: `true` se a resposta foi reenviada do cache (ver abaixo).
- `citadas`: números das fontes realmente citadas no texto.
- `aviso`: texto de aviso das guardas ("A resposta não citou nenhuma fonte...",
  "Confiança limitada pelo tipo de estudo...", "Modo degradado...") ou `null`.
- `consulta_id`: identificador para enviar em `/api/feedback`.

### Exemplo de fluxo

```text
data: {"tipo": "etapa", "texto": "Identificando a alegação"}
data: {"tipo": "alegacao", "texto": "...", "titulo_noticia": null}
data: {"tipo": "etapa", "texto": "Buscando estudos na base científica"}
data: {"tipo": "fontes", "fontes": [{"n": 1, "titulo": "...", "url": "https://pubmed.ncbi.nlm.nih.gov/.../", "ano": 2021, "tipos": ["Meta-Analysis"], "forca": "forte", "origem": "PubMed"}]}
data: {"tipo": "etapa", "texto": "Redigindo a análise"}
data: {"tipo": "veredito", "codigo": "...", "rotulo": "...", "confianca": "...", "resumo": "..."}
data: {"tipo": "texto", "texto": "..."}
data: {"tipo": "fim", "latencia_ms": 0, "modelo": "...", "do_cache": false, "citadas": [1], "aviso": null, "consulta_id": 1}
```

Os valores acima são só de forma; não são saída real.

### Cache

Dentro de `VOF_CACHE_HORAS`, a mesma entrada (mesmo texto normalizado e mesma versão da
base) recebe de volta os eventos da resposta anterior: `alegacao`, `estilo` e `fontes`
(se houve), `veredito` e `texto`, e então um `fim` com `do_cache: true` e uma nova
`consulta_id`. Não há eventos `etapa` nesse caso. Respostas em modo degradado não são
guardadas.

### Erros

| Situação | Resposta |
|---|---|
| `entrada` fora de 8 a 20.000 caracteres, ou corpo inválido | HTTP 422 |
| Limite de requisições por cliente excedido (`VOF_LIMITE_POR_MINUTO`, 12 por padrão) | HTTP 429, antes de abrir o fluxo |
| Página do link ilegível (login, paywall, bloqueio, URL recusada) | evento `erro` pedindo que o texto seja colado |
| Texto com menos de 12 caracteres depois de aparado | evento `erro` pedindo mais detalhe |
| Exceção inesperada | evento `erro` genérico ("Erro interno ao analisar"); o detalhe vai para o log |

O cliente é identificado pelo primeiro IP de `X-Forwarded-For`, quando existe; senão, pelo
endereço da conexão. O limite fica em memória e vale por processo.

### Modo degradado

Sem LLM configurado, ou com todos os modelos indisponíveis, a análise recupera as fontes
e responde `INCONCLUSIVA` com confiança `baixa` e `aviso` começando por "Modo
degradado". O fluxo termina normalmente, com `fim`.

## `POST /api/feedback`

```bash
curl -X POST http://localhost:7860/api/feedback \
  -H 'Content-Type: application/json' \
  -d '{"consulta_id": 1, "valor": 1}'
```

`valor` é um inteiro de -1 a 1 (1 positivo, -1 negativo). Resposta `{"ok": true}`, ou HTTP
404 se a consulta não existe (por exemplo, depois de um reinício que zerou o banco).

## `GET /api/saude`

```bash
curl http://localhost:7860/api/saude
```

Campos: `status` (`"ok"`), `documentos` (total na base), `llm` (se há LLM configurado),
`modelos` (lista de `LLM_MODELOS`, vazia sem LLM), `sinal_estilo` (se o BERTimbau está
carregado) e `base` com `gerado_em`, `artigos` e `sha256` do manifesto.

Na subida, o serviço começa a responder antes de terminar o aquecimento (indexação,
caso o banco esteja vazio, e carga dos modelos), que roda em segundo plano.

## `GET /api/destaques`

Temas em alta da semana, já checados. `atualizado_em` é um instante Unix, ou `null` se
ainda não houve rodada.

```json
{
  "atualizado_em": 1791420228.55,
  "temas": [
    {
      "alegacao": "Creatina faz mal para os rins",
      "origem": "curadoria",
      "veredito": "CONTESTADA",
      "confianca": "alta",
      "resumo": "Evidências de revisões sistemáticas mostram que a creatina não causa dano renal significativo.",
      "noticias": [{"titulo": "...", "url": "https://news.google.com/...", "fonte": "Metrópoles"}]
    }
  ]
}
```

`origem` é `curadoria` (planilha da equipe) ou `google_noticias`.

## `GET /api/metricas`

```bash
curl http://localhost:7860/api/metricas
```

| Campo | Significado |
|---|---|
| `consultas` | Total de consultas registradas desde que o banco foi criado |
| `respondidas_do_cache` | Quantas vieram do cache |
| `com_busca_ao_vivo` | Quantas precisaram ampliar a busca no PubMed |
| `feedback_positivo`, `feedback_negativo` | Contagem de feedback |
| `citacoes_validas_media` | Média de citações válidas por resposta gerada (não conta cache) |
| `latencia_ms_p50`, `latencia_ms_p95` | Percentis da latência das respostas geradas (não conta cache); `null` sem dados |
| `vereditos` | Contagem por código de veredito |
| `documentos_por_origem` | Documentos na base por origem (`lote`, `ao_vivo`) |

No deploy atual o banco fica num volume persistente, então os números acumulam desde a
primeira publicação. O uso desses sinais está em [Operação](operacao.md).

Os endpoints `/api/saude` e `/api/metricas` não têm autenticação.

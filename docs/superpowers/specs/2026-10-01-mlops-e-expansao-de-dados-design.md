# MLOps, expansão de dados e correção de viés — design

**Data:** 2026-10-01
**Status:** aprovado para planejamento de implementação
**Referência teórica:** Kreuzberger, Kühl & Hirschl, *Machine Learning Operations
(MLOps): Overview, Definition, and Architecture* (arXiv:2205.02302)

## Contexto e motivação

O projeto está na Fase 1 (PoC) + parte da Fase 2 (BERTimbau, NLI de suporte), mas
nunca foi avaliado contra um framework de MLOps. Ao cruzar o artigo de referência
com o estado real do código (não com o que a documentação promete), três lacunas
concretas apareceram:

1. **Nenhum dos 9 princípios de MLOps do artigo está implementado** além de
   versionamento de código (P5, colaboração) e parte de P3 (reprodutibilidade de
   dados, via hash do corpus). Faltam CI/CD (P1), orquestração (P2), versionamento
   de modelo (P4), metadata tracking (P7), monitoramento (P8) e feedback loops (P9).
2. **A Camada 2 (evidência científica) quase nunca roda.** Do recorte de saúde
   atual (350 notícias), apenas **3** têm o par medicamento+condição extraído
   (`dados/README.md`) — o vocabulário de 38 termos raramente casa com o texto.
3. **O viés de fonte da Camada 1 é conhecido mas não medido.** O Canvas já
   documenta que o modelo "mede em boa parte qual portal escreveu o texto" (G1 vs
   `diariodobrasil.org`), mas isso nunca foi quantificado com uma métrica formal —
   fica como suspeita qualitativa, não como gate de qualidade.

Este documento desenha a correção dessas três lacunas. Não cobre a licença DeCS
completa (exige contrato institucional via formulário BIREME/OPAS/OMS que ninguém
pode assinar nesta sessão) nem a expansão manual do vocabulário — ambos ficam
registrados como trabalho futuro na seção final.

## Fora de escopo (decidido explicitamente)

- Expansão do `vocabulario_seed.csv` (vocabulário PT/EN de medicamentos/condições).
- Integração com a API oficial do DeCS.
- Camada nova de fact-checking em tempo real (ex.: Google Fact Check Tools API) —
  o pedido original foi esclarecido como sendo sobre **dados de treino**, não uma
  camada de verificação adicional.
- Model registry remoto hospedado (MLflow server, HF Hub como registry) — fica
  para uma iteração futura se a equipe crescer além do que um commit de model card
  versionado no git resolve.
- Monitoramento de produção (P8) — não há deploy real ainda; não há o que
  monitorar além do que os testes já cobrem.

## Parte 1 — Expansão de dados: FakeRecogna como segunda fonte

### Problema

A "Onda 2" de coleta já estava planejada em `docs/dados.md` desde a Fase 1, mas
nunca foi executada. As fontes lá listadas (Aos Fatos, Lupa, Boatos.org) exigiriam
scraper customizado por site, sem rótulo pareado pronto.

### Fonte escolhida: `recogna-nlp/FakeRecogna` (Hugging Face)

Verificado nesta sessão via download direto do parquet:

- 11.903 linhas totais, **4.456 de categoria "saúde"** (1.136 falsas / 3.320
  verdadeiras).
- Formato **Parquet nativo** — carrega sem `load_dataset` com script, então não
  esbarra no problema já documentado (`datasets>=4.0` não executa scripts).
- Licença MIT.
- Colunas: `Titulo`, `Subtitulo`, `Noticia`, `Categoria`, `Data`, `Autor`, `URL`,
  `Classe` (0 = falsa, 1 = verdadeira).

### Achado crítico: o campo `Noticia` é inutilizável direto

O texto vem lematizado/stemizado pelo pipeline de pré-processamento dos autores
originais (ex.: `"o governar federal contar logístico gol e gollog levar
significativo dose vacinar"` em vez de "o governo federal conta com a logística da
Gol..."). Confirmado em múltiplas amostras de ambas as classes.

**Por que isso importa:** se esse texto entrasse direto no treino junto com o
Fake.br (texto natural), o modelo aprenderia a diferença de *registro textual
entre os dois datasets* — um atalho espúrio que infla a métrica sem ensinar nada
sobre desinformação. Seria repetir, de forma pior, o mesmo erro de viés de fonte
que o projeto já identificou no Fake.br.

### Solução: usar a tabela como índice (URL, rótulo), re-extrair o texto real

As URLs originais estão preservadas na tabela (ex.:
`https://www.boatos.org/saude/vacina-contra-covid-19-faz-imunidade-diminuir...`).
`verdade_ou_fake.ingestao.extrair_noticia` já existe e já sabe baixar + limpar HTML
via `trafilatura` — zero código novo nessa parte, só reuso.

### Novo script: `scripts/prepara_fakerecogna.py`

Espelha a estrutura e disciplina de `prepara_dataset.py`:

1. Baixa o parquet via URL fixa da API HF:
   `https://huggingface.co/api/datasets/recogna-nlp/FakeRecogna/parquet/default/train/0.parquet`
2. Filtra `Categoria == "saúde"`.
3. Para cada linha, chama `extrair_noticia(url)`. Se `None` (link morto, paywall,
   formato não suportado), descarta e conta.
4. Calcula e imprime a **taxa de extração bem-sucedida** (mesma prática do GQ8
   já existente para o `trafilatura` nos 20 links de teste).
5. Monta `id_par` sintético (não há pareamento fake/verdadeira no FakeRecogna como
   há no Fake.br — isso é uma diferença estrutural a documentar, não a forçar).
6. Salva em `dados/processed/saude_fakerecogna.csv`, schema compatível com
   `saude_ptbr.csv` (`id_par`, `texto`, `rotulo`, `categoria`), mais uma coluna
   `fonte` ("fakebr" | "fakerecogna") usada pela avaliação cross-source.
7. Hash de integridade do parquet baixado, seguindo o mesmo padrão de
   `impressao_digital`/`verificar_integridade` já usado para o Fake.br — para que
   o dataset gerado seja reproduzível mesmo que o parquet remoto mude.
8. Datasheet: nova seção em `dados/README.md`, preenchida com números reais só
   depois de rodar (nunca prometida antes).

### Uso no treino: duas rotinas, não uma

`scripts/treina_modelo.py` (e futuramente `treina_bert.py`) ganham uma segunda
rotina de avaliação, além do treino/teste já existente:

- **Treino combinado:** concatena Fake.br + FakeRecogna (mantendo split por
  `id_par`+`fonte` para não vazar).
- **Avaliação cross-source:** treina só no Fake.br, testa só no FakeRecogna; e
  vice-versa. Produz dois números de F1 macro cross-source que alimentam o model
  card (Parte 3).

Isso fecha a limitação "Leitura honesta" do Canvas com uma métrica concreta, em
vez de deixar como suspeita qualitativa.

## Parte 2 — Correção de viés: F1 cross-source como gate de qualidade

### Diagnóstico

A causa-raiz de "o modelo parece não entender a diferença entre notícia falsa e
verdadeira" não é falta de dado — é que o modelo aprende **sinal de fonte**
(estilo editorial do portal) em vez de **sinal de conteúdo** (padrões de
desinformação). Isso é mensurável: um modelo que aprendeu o portal terá F1 alto
"no mesmo dataset" e F1 baixo "no dataset de origem diferente, mesmo domínio
(saúde)".

### Métrica nova: `f1_macro_cross_source`

Calculada pela rotina de avaliação cross-source da Parte 1. Registrada no model
card (Parte 3) ao lado do F1 same-source já existente.

### Gate de aprovação

Um modelo só é promovido a `status: producao` no model card se:

```
f1_macro_same_source >= limiar_aprovacao.f1_macro_same_source_minimo  (ex.: 0.75)
E
(f1_macro_same_source - f1_macro_cross_source) <= limiar_aprovacao.queda_maxima_cross_source  (ex.: 0.20)
```

A segunda condição é a que detecta viés de fonte: uma queda grande entre
same-source e cross-source é a assinatura de um modelo que decorou o portal.

## Parte 3 — MLOps: model card versionado + CI/CD

### Por que não MLflow server / registry remoto

Decidido com o usuário: infraestrutura leve, sem servidor externo. MLflow local
(tracking em SQLite) continua disponível para uso individual do cientista de
dados durante ajuste de hiperparâmetros, mas **não é a fonte de verdade
compartilhada** — isso exigiria hospedar algo. A fonte de verdade compartilhada é
um arquivo versionado no git, pequeno, legível em diff por qualquer membro da
equipe sem rodar nada.

### Schema do model card

Arquivo `modelos/cards/<nome>.json`, versionado no git (diferente de
`modelos/*.joblib`, que continua fora do git por tamanho):

```json
{
  "nome": "baseline",
  "versao": "2026.10.01-a3f9c21",
  "tipo": "tfidf_logreg",
  "commit": "a3f9c21...",
  "dados": {
    "fontes": ["fakebr", "fakerecogna"],
    "hash_fakebr": "ce86b8f8...",
    "hash_fakerecogna": "<sha256 do parquet baixado>",
    "volume_treino": 1234,
    "volume_teste": 308
  },
  "metricas": {
    "f1_macro_same_source": 0.81,
    "f1_macro_cross_source_fakebr_para_fakerecogna": 0.58,
    "f1_macro_cross_source_fakerecogna_para_fakebr": 0.61
  },
  "limiar_aprovacao": {
    "f1_macro_same_source_minimo": 0.75,
    "queda_maxima_cross_source": 0.20
  },
  "status": "staging",
  "artefato_hash_sha256": "<hash do .joblib ou pasta do bertimbau>",
  "treinado_em": "2026-10-01T14:30:00-03:00",
  "treinado_por": "scripts/treina_modelo.py"
}
```

`status` ∈ `"staging"` (recém-treinado, aguardando revisão humana) |
`"producao"` (promovido manualmente, após revisão) | `"arquivado"`.

### Novo módulo: `src/verdade_ou_fake/model_card.py`

Funções puras + uma casca fina de I/O, seguindo o padrão já estabelecido em todo
o projeto (ex.: `ingestao.py`, `evidencia.py`):

- `calcular_hash_artefato(caminho: Path) -> str` — sha256 do arquivo/pasta do
  modelo.
- `montar_card(...) -> dict` — monta o dicionário acima a partir dos argumentos
  (pura, testável sem I/O).
- `salvar_card(card: dict, caminho: Path) -> None` / `carregar_card(caminho: Path)
  -> dict` — I/O fino.
- `aprovar_gate(card: dict) -> bool` — aplica a regra de `limiar_aprovacao`
  descrita na Parte 2 (pura, testável com cards sintéticos).

### `app.py` passa a validar o hash antes de servir

Ao carregar o modelo em produção, `app.py` lê
`modelos/cards/<nome>.json`, confere `status == "producao"` e recalcula o hash do
artefato em disco contra `artefato_hash_sha256`. Se não bater, mostra erro
explícito em vez de servir silenciosamente um modelo desatualizado ou corrompido.

### Workflows GitHub Actions

**`.github/workflows/ci.yml`** (novo) — todo push e PR:

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: pytest -m "not rede" -q
```

Rápido (minutos), sempre roda, nunca treina modelo pesado.

**`.github/workflows/treino-gate.yml`** (novo) — `workflow_dispatch` (manual) ou
gatilho automático quando `dados/vocabulario_seed.csv`,
`src/verdade_ou_fake/classificador.py` ou `src/verdade_ou_fake/fusao.py` mudam:

```yaml
name: Treino Gate
on:
  workflow_dispatch:
  push:
    paths:
      - 'dados/vocabulario_seed.csv'
      - 'src/verdade_ou_fake/classificador.py'
      - 'src/verdade_ou_fake/fusao.py'
jobs:
  treino:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: python scripts/prepara_dataset.py
      - run: python scripts/prepara_fakerecogna.py
      - run: python scripts/treina_modelo.py --cross-source
      - name: Verificar gate de qualidade
        run: python scripts/verifica_gate.py modelos/cards/baseline.json
      - uses: actions/upload-artifact@v4
        with:
          name: model-card-staging
          path: modelos/cards/baseline.json
```

O workflow **não commita o model card sozinho** — ele falha a execução
(bloqueando merge, no caso de PR) se o gate não passar, e sobe o card como
artifact para um humano revisar e decidir se promove `status: producao` via PR
manual. Trocar o modelo de produção é uma decisão da equipe, não automação cega
— coerente com o estágio atual do projeto (poucas pessoas, alta necessidade de
auditabilidade).

`scripts/verifica_gate.py` é um script fino: carrega o card recém-gerado, chama
`model_card.aprovar_gate`, e sai com código de erro se falhar — é o que o CI usa
para decidir vermelho/verde.

## Testes (seguindo TDD, padrão já estabelecido no projeto)

- `tests/test_model_card.py` — testa `montar_card`, `calcular_hash_artefato`
  (com arquivo temporário), `aprovar_gate` (casos: aprova, reprova por F1 baixo,
  reprova por queda cross-source, aprova no limite exato).
- `tests/test_prepara_fakerecogna.py` — testa a filtragem por categoria, a
  montagem do schema de saída e o cálculo de taxa de extração, com uma fixture
  local pequena do parquet (sem rede, seguindo a regra do projeto) e um
  `extrair_noticia` falso injetado (mesmo padrão de `buscar` em `pipeline.py`).
- `tests/test_treino_cross_source.py` — testa que a rotina cross-source separa
  corretamente por `fonte` e produz as duas métricas esperadas.

## Trabalho futuro (registrado, não implementado agora)

- **Licença DeCS completa.** Preencher o formulário institucional
  (`https://forms.office.com/r/ifyvmaf5bK`) para acesso à API/XML completo do
  DeCS — desbloqueia expansão de vocabulário além da curadoria manual.
- **Expansão manual do vocabulário** (~150-200 termos) como alternativa de curto
  prazo ao DeCS, se a equipe decidir que vale o esforço antes da licença sair.
- **Onda 3**: scraping direto de Aos Fatos/Lupa/Boatos.org para notícias de saúde
  sem equivalente no FakeRecogna, caso o volume ainda seja insuficiente após a
  Onda 2.
- **Monitoramento de produção (P8)** e **feedback loops (P9)** do artigo — fora
  de escopo até existir um deploy real com usuários.
- **Registry remoto** (MLflow hospedado ou HF Hub) se a equipe crescer além do
  que um model card versionado no git resolve confortavelmente.

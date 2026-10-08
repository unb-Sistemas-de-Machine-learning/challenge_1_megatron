# Dados do projeto

Dois conjuntos, com papéis diferentes:

| Conjunto | Papel hoje | Seção |
|---|---|---|
| Base de conhecimento do RAG (resumos do PubMed) | O sistema a **consulta** em cada resposta | [Datasheet da base](#datasheet--base-de-conhecimento-do-rag-resumos-do-pubmed) |
| Recorte de saúde PT-BR (Fake.br, FakeRecogna) | **Treino do classificador opcional** (BERTimbau, sinal de estilo) | [Datasheet do recorte](#datasheet--recorte-de-saúde-pt-br) |

Estrutura:

```
dados/
├── base/pubmed.jsonl         # base do RAG, versionada
├── base/manifesto.json       # data, volume e SHA-256 da base
├── vocabulario_seed.csv      # 23 medicamentos e 15 condições
├── raw/, processed/          # gerados pelos scripts de preparo (processed/saude_fakerecogna.csv é versionado)
└── vof.db                    # banco SQLite derivado (não vai para o git)
```

## Datasheet — Base de conhecimento do RAG (resumos do PubMed)

Esta é a base que o sistema consulta em cada resposta.

**Versão atual:** gerada em 2026-10-07 · **Script:** `scripts/ingere_pubmed.py` ·
**Arquivos:** `dados/base/pubmed.jsonl` (versionado no git) e `dados/base/manifesto.json`

| Campo do manifesto | Valor na versão atual |
|---|---|
| `fonte` | PubMed E-utilities |
| `gerado_em` | 2026-10-07 |
| `consultas` | 345 |
| `falhas` | 0 |
| `artigos` | 1069 |
| `sha256` | `73e8a4836cde39bc5959bbbb0230e0bf107715040da57c276fe2c135150ac7ee` |

O `sha256` é o hash do arquivo `pubmed.jsonl`. Ele entra na chave de cache e aparece em
`GET /api/saude`. A ingestão semanal reescreve o arquivo e o manifesto, então esta
tabela descreve a versão no momento da escrita; o manifesto é a fonte da verdade.

### Origem e coleta

- **Origem:** PubMed, pela API E-utilities do NCBI (`esearch` para os identificadores,
  `efetch` para os resumos). Gratuita; a chave `NCBI_API_KEY` é opcional e sobe o limite
  de requisições.
- **O que se busca:** uma consulta por medicamento do vocabulário e uma por par
  medicamento × condição. O vocabulário (`dados/vocabulario_seed.csv`) tem 23
  medicamentos e 15 condições (14 termos distintos em inglês, porque "covid" e
  "covid-19" apontam para o mesmo). São 23 + 23 × 14 = 345 consultas.
- **Quantos por consulta:** até 12 artigos por medicamento e até 6 por par.

### Critério de inclusão

- Tipo de publicação: revisão sistemática, meta-análise ou ensaio clínico randomizado
  (`systematic review[pt] OR meta-analysis[pt] OR randomized controlled trial[pt]`).
- Exclusão de estudos só em animais (`NOT (animals[mh] NOT humans[mh])`).
- Termos buscados em título ou resumo.
- Mantidos só artigos com PMID e resumo de pelo menos 200 caracteres. Duplicatas por PMID
  são removidas.
- Os artigos que chegam pela busca ao vivo durante o uso (origem `ao_vivo`) **não** passam
  por esses filtros de lote: aceitam qualquer tipo de estudo quando não há estudo forte.
  Eles ficam só no banco em execução, não neste arquivo.

### Conteúdo

Um artigo por linha, com `pmid`, `titulo`, `resumo`, `tipos_estudo` (tipos de publicação
do PubMed) e `ano`. Na versão atual os anos vão de 1976 a 2026. Entre os tipos de
publicação: 530 ensaios randomizados, 477 revisões sistemáticas e 297 meta-análises (um
artigo pode ter mais de um tipo).

### Idioma

Resumos principalmente em inglês, a língua da literatura biomédica indexada. A busca não
filtra por idioma. A alegação do usuário chega em português, e a ponte é o modelo de
embeddings multilíngue ([ADR 0003](../docs/adr/0003-embeddings-multilingues-onnx.md)).

### Licença e termos de uso

Os metadados do PubMed são mantidos pela National Library of Medicine (NLM). Os resumos
podem ter direitos autorais dos editores e dos autores. Usamos a base para pesquisa e
ensino. A interface mostra apenas o título, o tipo de estudo e o link para o PubMed,
mas o arquivo `dados/base/pubmed.jsonl`, versionado neste repositório público, contém o
texto dos resumos, e trechos deles são enviados ao provedor de LLM a cada consulta. Esse
uso precisa ser revisto antes de qualquer aplicação fora do contexto acadêmico. Os
termos vigentes estão nas políticas do NCBI
(<https://www.ncbi.nlm.nih.gov/home/about/policies/>) e nos termos de uso dos dados da
NLM (<https://www.nlm.nih.gov/databases/download/terms_and_conditions.html>). Quem for
reutilizar o arquivo deve conferir esses termos.

### Vieses e limitações conhecidos

- **Literatura em inglês.** Estudos publicados em outros idiomas e a prática clínica
  brasileira ficam sub-representados.
- **Viés de publicação.** Estudos com resultado positivo são mais publicados do que os
  negativos, então a base pode exagerar a eficácia dos tratamentos.
- **Cobertura restrita ao vocabulário.** Só medicamentos e condições do vocabulário (23 e
  15) são ingeridos em lote. O que mais entrar vem da busca ao vivo, que cobre pior e
  não é persistida no plano gratuito de hospedagem.
- **Resumos, não texto completo.** O resumo pode omitir limitações, subgrupos e conflitos
  de interesse que mudariam a leitura do estudo.
- **Seleção por relevância do PubMed.** O corte de 12 e 6 artigos por consulta, ordenados
  por relevância, pode deixar estudos importantes de fora.
- **Sem avaliação de qualidade individual.** O tipo de publicação é um proxy do nível de
  evidência. Uma revisão sistemática ruim conta como forte, e um ensaio pequeno também.
- **Sem tratamento de retratações.** O filtro de ingestão não remove publicações
  retratadas.
- **Vocabulário tem viés de seleção.** Foi escolhido pela equipe, não por frequência de
  uso ou de desinformação medida.

### Como regenerar

```bash
python scripts/ingere_pubmed.py              # ingestão completa
python scripts/ingere_pubmed.py --limite 5   # teste rápido, só 5 consultas
python scripts/constroi_base.py              # (re)constrói o banco SQLite a partir do JSONL
```

O workflow `ingestao-base.yml` roda a ingestão toda semana e commita a base atualizada.

---

## Datasheet — Recorte de saúde PT-BR

> **Papel atual:** dado de treino do classificador opcional (BERTimbau). Não alimenta o veredito do RAG.

**Versão:** 1.0 · **Gerado em:** 2026-09-24 · **Script:** `scripts/prepara_dataset.py`

### Como gerar

```bash
python scripts/prepara_dataset.py            # baixa o corpus em dados/raw/fakebr
python scripts/prepara_dataset.py --corpus PASTA   # usa uma cópia local já extraída
```

Saída: `dados/processed/saude_ptbr.csv`. As pastas `dados/raw/` e `dados/processed/`
não vão para o git; o script as recria do zero.

### Origem

Fake.br Corpus, repositório oficial
[roneysco/Fake.br-Corpus](https://github.com/roneysco/Fake.br-Corpus), **fixado no
commit `780f5516c4ae070761632d98ac3368f3ded09d35`** (último commit, 2020-10-30).
São 3600 pares alinhados de notícias falsas e verdadeiras em português, coletadas
entre 2016 e 2018.

**Por que não o Hugging Face:** o espelho `fake-news-UFG/fakebr` não tem arquivos
de dados, só um script de carga (`fakebr.py`). A biblioteca `datasets` deixou de
executar scripts na versão 4.0, então `load_dataset("fake-news-UFG/fakebr")` falha
com `RuntimeError: Dataset scripts are no longer supported`.

**Integridade:** depois do download, o script calcula o SHA-256 dos caminhos e do
conteúdo dos 14.400 arquivos usados e compara com
`ce86b8f8d74ec6086a7a9d0018e2e681ea022d88560ac5aaccc914e383df7d29`. Se não
conferir, o script para. O hash é do conteúdo, não do `.zip`, porque o GitHub pode
mudar a compressão dos pacotes sem aviso.

### Colunas

| Coluna | Descrição |
|---|---|
| `id_par` | Número do par no Fake.br. A falsa e a verdadeira de mesmo `id_par` tratam do mesmo assunto. |
| `texto` | Texto da versão `size_normalized_texts`, em UTF-8, sem BOM e com quebra de linha `\n`. |
| `rotulo` | **1 = desinformação (fake), 0 = legítima (true).** É a convenção do projeto. No script do Hugging Face o `ClassLabel` era o inverso: fake = 0. |
| `categoria` | Categoria do metadado original (`politica`, `tv_celebridades`, ...). |

### Decisões de preparação

- **Textos normalizados por tamanho.** Nos `full_texts`, a mediana é de 918 palavras
  nas verdadeiras e 157 nas falsas. Um classificador aprenderia "texto longo =
  verdadeiro". Na versão `size_normalized_texts`, cada par foi truncado ao tamanho
  do menor texto. No recorte, a mediana ficou em 199 palavras nas verdadeiras e 200
  nas falsas.
- **Pares completos.** Uma notícia entra no recorte se ela ou o seu par mencionar um
  termo de saúde, e as duas metades entram juntas. Com isso as classes ficam
  balanceadas e o treino pode dividir os dados por `id_par` sem vazar o assunto
  entre treino e teste (ver Task 6).
- **Filtro.** Ao menos um termo de `dados/vocabulario_seed.csv` (medicamento ou
  condição), casado por fronteira de palavra e ignorando acento e caixa.

### Volume

- Corpus completo: 7200 notícias (3600 falsas, 3600 verdadeiras)
- Notícias que mencionam termo de saúde: 198 (117 falsas, 81 verdadeiras)
- **Recorte final: 350 notícias em 175 pares (175 falsas, 175 verdadeiras)**
- Por categoria: política 130, tv_celebridades 126, sociedade_cotidiano 84,
  ciencia_tecnologia 10
- Termos mais frequentes (em notícias): câncer 95, depressão 39, dengue 21,
  ansiedade 12, hipertensão 8, diabetes 8
- Notícias com o par medicamento + condição (`extrair_alegacao`): **3**

### Limitações conhecidas

- **A decisão D2 falhou na prática.** O recorte passa de 300 notícias, mas quase não
  trata de saúde. O Fake.br não tem categoria de saúde, e os termos mais frequentes
  aparecem fora do sentido médico ("depressão causada pela delação", "ansiedade em
  relação a essas delações"). Só 3 notícias citam medicamento e
  condição juntos. É preciso acionar a **Onda 2 de coleta** (agências de checagem,
  FakeRecogna), descrita em [Fontes de Dados](../docs/dados.md).
- **Sem COVID-19.** O corpus é de 2016–2018, então nenhuma notícia menciona covid,
  o tema de desinformação em saúde mais comum desde 2020.
- **Defeitos do corpus original, tratados no script:**
  - Os pares 697 e 1468 da versão normalizada não têm arquivo de metadados. Eles
    entram com `categoria = desconhecida`.
  - 26 arquivos de metadados têm a primeira linha (autor) em branco. A leitura é
    feita por linha, sem `strip()` no arquivo inteiro, para não deslocar os campos.
  - Parte dos arquivos tem BOM UTF-8 e quebras de linha CRLF.
- **O vocabulário semente tem 38 termos**, então medicamentos fora da lista não são
  capturados.
- **Viés de fonte forte.** 3337 das 3600 falsas (93%) vêm de `diariodobrasil.org`;
  das verdadeiras, 2300 vêm de `g1.globo.com` e a maior parte do resto do Estadão.
  O modelo pode aprender o estilo editorial de cada site em vez de sinais de
  desinformação. Por isso é essencial testar em notícias de outras fontes.

### Segunda fonte: FakeRecogna (Onda 2)

**Origem:** [recogna-nlp/FakeRecogna](https://huggingface.co/datasets/recogna-nlp/FakeRecogna)
(Hugging Face, licença MIT), categoria "saúde" (4.456 notícias na fonte original).

**Por que não usar o texto da tabela direto:** o campo `Noticia` vem lematizado
pelo pipeline de pré-processamento dos autores originais (ex.: "o governar
federal contar logístico" em vez de "o governo conta com a logística"). Misturar
isso com o texto natural do Fake.br ensinaria o modelo a distinguir o *dataset de
origem*, não fake/real. Em vez disso, `scripts/prepara_fakerecogna.py` usa a
tabela como índice (URL + rótulo) e reextrai o texto original via
`ingestao.extrair_noticia` — a mesma função que já serve a etapa [0] do pipeline.

**Como gerar:**

```bash
python scripts/prepara_fakerecogna.py
```

Saída: `dados/processed/saude_fakerecogna.csv`, commitado no git (diferente do
`saude_ptbr.csv`, que é regenerado em segundos a partir de um commit fixo do
Fake.br — o FakeRecogna depende de milhares de requisições de rede a sites de
terceiros, não regenerável a cada execução do CI).

**Mapeamento de rótulo:** no FakeRecogna, `Classe=0.0` é falsa e `Classe=1.0` é
real — invertido em relação à convenção do projeto (`rotulo=1` é desinformação).
O script já faz essa conversão.

**Volume e taxa de extração:** não medidos. `scripts/prepara_fakerecogna.py` não foi
rodado até o fim, e `dados/processed/saude_fakerecogna.csv` não existe no repositório.
O classificador em uso foi treinado só com o recorte do Fake.br.

# Dados

O projeto usa dois conjuntos de dados, com papéis diferentes:

| Conjunto | Papel hoje | Onde está |
|---|---|---|
| **Base de conhecimento do RAG**: resumos de estudos do PubMed | É o que o sistema **consulta** em cada resposta | `dados/base/pubmed.jsonl` |
| **Recorte de saúde do Fake.br** (e, opcionalmente, FakeRecogna) | Dado de **treino do classificador opcional** (BERTimbau, sinal de estilo) | gerado por `scripts/prepara_dataset.py` |

Na versão anterior do sistema, o corpus rotulado era o centro do projeto. Hoje o
veredito vem da evidência recuperada, e o corpus rotulado só alimenta o sinal secundário
([ADR 0009](adr/0009-bertimbau-sinal-secundario.md)). Confundir os dois foi o que travou
o início do projeto: a verificação por evidência não precisa de dataset de treino, e sim
de acesso a fontes confiáveis.

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
embeddings multilíngue ([ADR 0003](adr/0003-embeddings-multilingues-onnx.md)).

### Licença e termos de uso

Os metadados do PubMed são mantidos pela National Library of Medicine (NLM). Os resumos
podem ter direitos autorais dos editores e dos autores. Usamos a base para pesquisa e
ensino, mostramos apenas o título, o tipo de estudo e o link para o PubMed, e não
redistribuímos os resumos como produto. Os termos vigentes estão nas políticas do NCBI
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

## Bases científicas e vocabulários

| Base | Papel | Situação |
|---|---|---|
| [PubMed](https://www.ncbi.nlm.nih.gov/books/NBK25501/) | Literatura biomédica revisada por pares | **Usada**: ingestão semanal em lote e busca ao vivo (E-utilities, gratuito) |
| Vocabulário semente (`dados/vocabulario_seed.csv`) | 23 medicamentos e 15 condições, com termo em português e em inglês | **Usado**: define o que a ingestão em lote cobre e serve de reserva na identificação da alegação |
| [DeCS](https://decs.bvsalud.org/) | Vocabulário PT/EN/ES, ponte para o MeSH | Cogitado no desenho inicial; **não usado** |
| [DCB/ANVISA](https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/dcb) | Nomenclatura oficial de princípios ativos | Cogitado; **não usado** |
| Cochrane | Revisões sistemáticas | Cogitado; **não usado** (acesso não confirmado) |
| ClinicalTrials.gov | Registro de ensaios clínicos | Cogitado; **não usado** |

A ponte entre português e inglês, que o DeCS faria, hoje é feita pelo modelo de
embeddings multilíngue e pela tradução da alegação feita pelo LLM
([ADR 0003](adr/0003-embeddings-multilingues-onnx.md)).

## Critérios de inclusão de evidência

A hierarquia de evidência usada na recuperação e no teto de confiança:

1. Revisão sistemática ou meta-análise (bônus de 1,20 na busca; permite confiança alta)
2. Ensaio clínico randomizado (bônus de 1,08; limita a confiança a média)
3. Qualquer outro tipo de estudo (sem bônus; limita a confiança a baixa)

Estudos conflitantes sobre o mesmo par medicamento/doença devem resultar em veredito
`INCONCLUSIVA`, não na escolha de um lado: é o que o prompt de veredito pede ao LLM. O critério de ingestão em lote está no datasheet acima.

## Governança dos dados

- **Datasheets.** Cada conjunto documenta origem, critério, volume e limitações, nos
  moldes de *Datasheets for Datasets* (Gebru et al.): acima para a base do RAG; o do
  recorte do Fake.br está em
  [`dados/README.md`](https://github.com/unb-Sistemas-de-Machine-learning/challenge_1_megatron/blob/main/dados/README.md).
- **Proveniência.** Cada artigo da base guarda o PMID e a URL do PubMed. Cada resposta
  registra as fontes usadas na tabela `consultas`.
- **Versionamento.** A base é um JSONL no git, com manifesto e SHA-256. O hash entra na
  chave de cache, então atualizar a base invalida as respostas guardadas.
- **Privacidade.** `consultas` guarda a alegação extraída, as fontes, a resposta gerada e uma chave de hash
  da entrada (não o texto bruto digitado); `paginas` guarda o texto extraído de links. No plano gratuito do Space, esse registro zera a cada reinício.

## Riscos conhecidos

| Risco | Impacto | Mitigação |
|---|---|---|
| Cobertura restrita ao vocabulário | Alegações fora dele dependem da busca ao vivo | Ampliar o vocabulário; consultas com busca ao vivo apontam as lacunas |
| Viés de publicação e literatura em inglês | A base pode exagerar a eficácia e sub-representar o contexto brasileiro | Declarado no datasheet; revisões sistemáticas pesam mais |
| Resumo no lugar do texto completo | Limitações do estudo podem ficar de fora | Mostrar sempre o link para o estudo |
| Fontes de dados mudam | O PubMed é atualizado continuamente | Ingestão semanal e hash na chave de cache |
| Viés de fonte no corpus de treino (classificador opcional) | O modelo aprende o portal, não o conteúdo | O classificador deixou de decidir o veredito |

O viés de fonte do corpus de treino foi o mais traiçoeiro: se toda notícia falsa vem de
um site e toda verdadeira de portais grandes, o modelo aprende a reconhecer o **portal**,
e a métrica fica excelente enquanto o sistema é inútil. Foi o que aconteceu com o
BERTimbau (ver [Arquitetura](arquitetura.md#o-que-mudou-e-por-que)).

---

## Datasets de notícias (treino do classificador opcional)

!!! note "Papel atual desta seção"
    Esta parte descreve o levantamento de datasets de notícias feito para treinar o
    classificador de estilo. Esse classificador agora é um sinal secundário opcional.
    O levantamento fica como registro do processo e porque o recorte do Fake.br ainda é
    o dado de treino do BERTimbau. O model card registra que o treino atual usou só o Fake.br.

### O achado central: o buraco "saúde + português"

**Não existe dataset pronto de fake news de saúde em português.** Levantamento das
opções disponíveis:

#### Em português, domínio geral

| Corpus | Volume | Acesso | Cobre saúde? |
|---|---|---|---|
| [Fake.br Corpus](https://huggingface.co/datasets/fake-news-UFG/fakebr) | 7.200 instâncias balanceadas | Hugging Face, `load_dataset` imediato | Parcialmente, sem recorte explícito |
| [FakeRecogna](https://link.springer.com/chapter/10.1007/978-3-030-98305-5_6) | 5.951 falsas + 5.951 verdadeiras | [Repositório UNESP](https://repositorio.unesp.br/handle/11449/234317) | **Sim** — saúde/COVID entre as categorias mais fortes |
| FakeTrueBR | — | Publicação acadêmica | Não segmentado |
| Fakepedia Corpus | — | Publicação acadêmica | Não segmentado |

#### Em inglês, específico de saúde

| Corpus | Conteúdo | Acesso |
|---|---|---|
| [FakeHealth](https://github.com/EnyanDai/FakeHealth) | Notícias de saúde avaliadas por especialistas, vários temas médicos | GitHub |
| [CoAID](https://github.com/cuilimeng/CoAID) | 4.251 notícias + 296 mil engajamentos sobre COVID-19 | GitHub |
| [ReCOVery](https://github.com/apurvamulay/ReCOVery) | Notícias sobre COVID com rótulo de credibilidade da fonte | GitHub |

O recorte que o projeto precisa — **saúde E português** — é exatamente a interseção
vazia. Isso não é azar: em Amershi et al., *Data Availability, Collection, Cleaning and
Management* é o desafio nº 1 em **todos** os níveis de experiência (Tabela II), e cresce
60% em frequência entre os engenheiros mais experientes.

### Estratégia adotada (histórico)

Português desde o início, em duas ondas:

**Onda 1 — filtrar o que já existe.** Extrair o subconjunto de saúde do FakeRecogna e
do Fake.br por palavras-chave do vocabulário DeCS/DCB. Disponível para download
imediato, permite treinar o baseline na primeira semana.

**Onda 2 — ampliar com coleta própria.** Complementar com checagens brasileiras já
publicadas sobre saúde:

| Fonte | Tipo |
|---|---|
| [Aos Fatos](https://aosfatos.org/) | Agência de checagem, seção de saúde |
| [Agência Lupa](https://lupa.uol.com.br/) | Agência de checagem |
| [Boatos.org](https://boatos.org/) | Catálogo de boatos, categoria saúde |
| [Saúde sem Fake News](https://www.gov.br/saude/pt-br/assuntos/fake-news) | Ministério da Saúde, desmentidos oficiais |

Os corpora em inglês ficam como **referência de validação** — para comparar métricas
com baselines publicados — e não entram no treino.

#### Por que não treinar em inglês e traduzir

Foi considerado e descartado: com dataset traduzido, um erro de classificação pode vir
do modelo, da tradução ou da diferença de domínio, e a equipe não teria como saber
qual. Para um time iniciante, essa ambiguidade custa mais tempo do que o volume extra
de dados economiza.


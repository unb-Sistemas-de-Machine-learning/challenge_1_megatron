# Fontes de Dados

O projeto usa dois tipos de dado, com finalidades distintas:

- **Corpus rotulado de notícias** — treina a Camada 1 (risco textual).
- **Bases científicas e vocabulários** — alimentam a Camada 2 (verificação por evidência). Não são treinadas, são **consultadas**.

Confundir os dois foi o que travou o início do projeto. A Camada 2 não precisa de
dataset de treino; ela precisa de acesso a fontes confiáveis.

## O achado central: o buraco "saúde + português"

**Não existe dataset pronto de fake news de saúde em português.** Levantamento das
opções disponíveis:

### Em português, domínio geral

| Corpus | Volume | Acesso | Cobre saúde? |
|---|---|---|---|
| [Fake.br Corpus](https://huggingface.co/datasets/fake-news-UFG/fakebr) | 7.200 instâncias balanceadas | Hugging Face, `load_dataset` imediato | Parcialmente, sem recorte explícito |
| [FakeRecogna](https://link.springer.com/chapter/10.1007/978-3-030-98305-5_6) | 5.951 falsas + 5.951 verdadeiras | [Repositório UNESP](https://repositorio.unesp.br/handle/11449/234317) | **Sim** — saúde/COVID entre as categorias mais fortes |
| FakeTrueBR | — | Publicação acadêmica | Não segmentado |
| Fakepedia Corpus | — | Publicação acadêmica | Não segmentado |

### Em inglês, específico de saúde

| Corpus | Conteúdo | Acesso |
|---|---|---|
| [FakeHealth](https://github.com/EnyanDai/FakeHealth) | Notícias de saúde avaliadas por especialistas, vários temas médicos | GitHub |
| [CoAID](https://github.com/cuilimeng/CoAID) | 4.251 notícias + 296 mil engajamentos sobre COVID-19 | GitHub |
| [ReCOVery](https://github.com/apurvamulay/ReCOVery) | Notícias sobre COVID com rótulo de credibilidade da fonte | GitHub |

O recorte que o projeto precisa — **saúde E português** — é exatamente a interseção
vazia. Isso não é azar: em Amershi et al., *Data Availability, Collection, Cleaning and
Management* é o desafio nº 1 em **todos** os níveis de experiência (Tabela II), e cresce
60% em frequência entre os engenheiros mais experientes.

## Estratégia adotada

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

### Por que não treinar em inglês e traduzir

Foi considerado e descartado: com dataset traduzido, um erro de classificação pode vir
do modelo, da tradução ou da diferença de domínio, e a equipe não teria como saber
qual. Para um time iniciante, essa ambiguidade custa mais tempo do que o volume extra
de dados economiza.

## Bases consultadas pela Camada 2

Não são treinadas. São consultadas em tempo de execução.

| Base | Papel | Acesso |
|---|---|---|
| [PubMed](https://www.ncbi.nlm.nih.gov/books/NBK25501/) | Literatura biomédica revisada por pares | E-utilities, grátis, sem chave obrigatória |
| [DeCS](https://decs.bvsalud.org/) | Vocabulário PT/EN/ES, ponte para o MeSH | Portal BVS |
| [DCB/ANVISA](https://www.gov.br/anvisa/pt-br/assuntos/farmacopeia/dcb) | Nomenclatura oficial de princípios ativos no Brasil | Lista consolidada |
| Cochrane | Revisões sistemáticas e meta-análises | Avaliar acesso institucional |
| ClinicalTrials.gov | Registro de ensaios clínicos | API pública |

!!! note "PubMed e Cochrane primeiro"
    PubMed é a espinha dorsal: cobertura ampla, API estável, gratuita. Cochrane entra
    quando o acesso for confirmado — revisões sistemáticas são o topo da hierarquia de
    evidência e valem mais que dez estudos isolados.

## Critérios de inclusão de evidência

Nem todo artigo do PubMed tem o mesmo peso. A ordem de prioridade na recuperação:

1. Revisão sistemática ou meta-análise
2. Ensaio clínico randomizado
3. Estudo observacional (coorte, caso-controle)
4. Relato de caso, estudo *in vitro* ou em animais — sinalizados como evidência fraca

Publicações retratadas são descartadas. Estudos conflitantes sobre o mesmo par
medicamento/doença resultam em **"evidência contestada"**, não em escolha arbitrária de
um lado.

## Governança dos dados

Amershi et al. tratam versionamento e rastreabilidade de dados como diferença
fundamental entre engenharia de software e ML (Seção VII-A). Aplicado aqui:

- **Datasheet do dataset.** Cada versão do recorte de saúde documenta origem, critério de filtragem, volume por classe e limitações conhecidas — nos moldes de *Datasheets for Datasets* (Gebru et al., referência [34] do artigo-base).
- **Proveniência.** Cada exemplo mantém a fonte original e a data de coleta.
- **Versionamento.** Dataset versionado junto com o código que o gerou, para que qualquer resultado seja reproduzível.

## Riscos conhecidos

| Risco | Impacto | Mitigação |
|---|---|---|
| Recorte de saúde pequeno demais | Modelo com alta variância | Onda 2 de coleta; reportar intervalo de confiança das métricas |
| Viés temporal (COVID domina) | Não generaliza para outros medicamentos | Medir desempenho por tema; balancear na Onda 2 |
| Viés de fonte | Modelo aprende o portal, não o conteúdo | Remover marcadores de domínio; avaliar em portais não vistos no treino |
| Desbalanceamento de classes | Métrica enganosa | Reportar F1 por classe, nunca acurácia isolada |

O viés de fonte é o mais traiçoeiro: se toda notícia falsa vier do Boatos.org e toda
verdadeira de portais grandes, o modelo aprende a reconhecer o **portal**, e a métrica
fica excelente enquanto o sistema é inútil. A avaliação em portais fora do treino
existe para detectar isso.

# Datasheet — Recorte de saúde PT-BR

**Versão:** 1.0 · **Gerado em:** 2026-09-24 · **Script:** `scripts/prepara_dataset.py`

## Como gerar

```bash
python scripts/prepara_dataset.py            # baixa o corpus em dados/raw/fakebr
python scripts/prepara_dataset.py --corpus PASTA   # usa uma cópia local já extraída
```

Saída: `dados/processed/saude_ptbr.csv`. As pastas `dados/raw/` e `dados/processed/`
não vão para o git; o script as recria do zero.

## Origem

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

## Colunas

| Coluna | Descrição |
|---|---|
| `id_par` | Número do par no Fake.br. A falsa e a verdadeira de mesmo `id_par` tratam do mesmo assunto. |
| `texto` | Texto da versão `size_normalized_texts`, em UTF-8, sem BOM e com quebra de linha `\n`. |
| `rotulo` | **1 = desinformação (fake), 0 = legítima (true).** É a convenção do projeto. No script do Hugging Face o `ClassLabel` era o inverso: fake = 0. |
| `categoria` | Categoria do metadado original (`politica`, `tv_celebridades`, ...). |

## Decisões de preparação

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

## Volume

- Corpus completo: 7200 notícias (3600 falsas, 3600 verdadeiras)
- Notícias que mencionam termo de saúde: 198 (117 falsas, 81 verdadeiras)
- **Recorte final: 350 notícias em 175 pares (175 falsas, 175 verdadeiras)**
- Por categoria: política 130, tv_celebridades 126, sociedade_cotidiano 84,
  ciencia_tecnologia 10
- Termos mais frequentes (em notícias): câncer 95, depressão 39, dengue 21,
  ansiedade 12, hipertensão 8, diabetes 8
- Notícias com o par medicamento + condição (`extrair_alegacao`): **3**

## Limitações conhecidas

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

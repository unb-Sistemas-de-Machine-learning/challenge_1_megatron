# CANVAS — DA PERGUNTA CERTA AO OBJETIVO CERTO
Canvas de planejamento do projeto, conectando as perguntas norteadoras (guiding
questions) às atividades práticas que respondem cada uma, além dos objetivos
de negócio e de ML e do escopo do sistema.
## 1. Guiding Questions

### Dados
| # | Pergunta | Atividade | Recurso | Responsável | Prazo | Resposta encontrada |
|---|----------|-----------|---------|--------------|-------|---|
| GQ1 | Quais fontes usaremos (PubMed, Cochrane, ANVISA, FDA, ClinicalTrials.gov) e como garantir que sejam confiáveis e atualizadas? | Mapear e testar acesso via API/scraping a cada base; definir critério de corte (revisão por pares, tipo de estudo, data). | Documentação das APIs (PubMed E-utilities, Cochrane Library, ANVISA Bulário) | Membro 1 | 24/08 | Parcial. PubMed como fonte única; critério de inclusão: revisão sistemática, meta-análise e ensaio randomizado, sem estudos só em animais; base atualizada por ingestão semanal. Cochrane, ANVISA, FDA e ClinicalTrials.gov não foram usados. |
| GQ2 | Como padronizar métricas de eficácia (taxa de resposta, NNT, redução de sintomas) que vêm em formatos diferentes entre estudos? | Coletar amostra de 15-20 artigos sobre 2-3 medicamentos e catalogar como cada um reporta eficácia. | Artigos de meta-análise já publicados como referência de padronização | Membro 2 | 31/08 | Não respondida. O sistema não padroniza nem calcula métricas de eficácia; o LLM resume qualitativamente o que os resumos dizem. |


### Usuário
| # | Pergunta | Atividade | Recurso | Responsável | Prazo | Resposta encontrada |
|---|----------|-----------|---------|--------------|-------|---|
| GQ3 | O usuário cola o **link da notícia** — que nível de linguagem torna a resposta compreensível sem simplificar demais a ciência? | Entrevistar 5-8 pessoas leigas mostrando 2 formatos de resposta (técnico vs. simplificado) e comparar compreensão. | Roteiro de entrevista curto + protótipo de tela de resposta | Membro 3 | 27/08 | Parcial. O prompt exige português para leigos, sem jargão. Não há registro, neste repositório, de teste de compreensão com usuários. |
| GQ8 | O extrator de texto funciona nos portais de notícia brasileiros que importam? | Rodar `trafilatura` contra 20 links reais de portais diferentes e medir taxa de extração limpa. | Lista de links de teste + biblioteca `trafilatura` | Membro 3 | 31/08 | Parcial. Quando a página não abre, o sistema pede que o usuário cole o texto, e a entrada por texto colado existe por isso. A taxa de extração nos portais não está registrada neste repositório. |

### Modelo
| # | Pergunta | Atividade | Recurso | Responsável | Prazo | Resposta encontrada |
|---|----------|-----------|---------|--------------|-------|---|
| GQ4 | Como agregar resultados de múltiplos estudos de forma estatisticamente responsável (meta-análise simplificada, ponderação por qualidade)? | Testar 1-2 métodos de agregação (média ponderada por tamanho de amostra/qualidade) em um caso real e comparar com meta-análise publicada do mesmo tema. | Biblioteca de meta-análise em Python (statsmodels, metafor via R) + 1 meta-análise Cochrane como gabarito | Membro 4 | 07/09 | Não respondida. Não há agregação estatística; o tipo de estudo pesa na busca (bônus) e no teto de confiança. |
| GQ5 | Como evitar que o modelo "alucine" citações ou dados que não existem? | Rodar testes com prompts adversariais/casos sem evidência e verificar se o sistema inventa fontes; definir mecanismo de citação obrigatória (RAG com link à fonte original). | Conjunto de perguntas-teste com respostas conhecidas (algumas sem evidência disponível de propósito) | Membro 1 | 09/09 | Sim. Citação obrigatória, remoção de citações inexistentes, rebaixamento de veredito sem citação e teto de confiança pelo tipo de estudo ([ADR 0007](adr/0007-guardas-deterministicas.md)). As guardas não garantem que a citação sustente a frase. |


### Ética
| # | Pergunta | Atividade | Recurso | Responsável | Prazo | Resposta encontrada |
|---|----------|-----------|---------|--------------|-------|---|
| GQ6 | Como deixar claro que o sistema não substitui orientação médica e evitar reforçar desinformação já repetida? | Desenhar o disclaimer e o fluxo de resposta para casos de "sem evidência"/"evidência contestada"; revisar com base em diretrizes de comunicação em saúde. | Guidelines de comunicação de risco em saúde (OMS, CDC) | Membro 2 | 31/08 | Parcial. Aviso de que o sistema não substitui orientação médica na interface; as respostas `NAO_VERIFICAVEL` e `INCONCLUSIVA` dizem que falta de estudo não prova falsidade. Não houve revisão externa do fluxo. |


### Produção
| # | Pergunta | Atividade | Recurso | Responsável | Prazo | Resposta encontrada |
|---|----------|-----------|---------|--------------|-------|---|
| GQ7 | Como o sistema será atualizado com novos artigos e evidências ao longo do tempo? | Desenhar um pipeline simples de ingestão periódica (ex: consulta semanal à API do PubMed por medicamento cadastrado). | Estrutura de pipeline de dados (cron job / agendador + banco vetorial) | Membro 3 | 07/09 | Sim. Ingestão semanal do PubMed pelo workflow `ingestao-base.yml` e busca ao vivo quando a base não cobre a alegação ([ADR 0006](adr/0006-base-em-lote-com-busca-ao-vivo.md)). |


## 2. Objetivos do Negócio
Dor: Pessoas leem notícias sobre medicamentos e não sabem se há base científica real, podendo se automedicar ou tomar decisões de saúde com base em informação exagerada/falsa.

Objetivo de negócio: Reduzir decisões de saúde tomadas com base em notícias sem respaldo científico — medível no MUNDO (ex.: % de usuários que, após consultar o sistema, afirmam ter mudado de ideia sobre confiar/agir sobre a notícia; redução autorrelatada de intenção de automedicação).


## 3. Objetivos de ML

O sistema atual é um RAG ([Arquitetura](arquitetura.md)). O objetivo de ML tem **duas
partes mensuráveis**:

1. **Recuperar estudos relevantes para a alegação.** Dada a alegação, a busca híbrida
   deve trazer os estudos que a tratam.
2. **Redigir um veredito fiel às fontes.** O texto deve se apoiar só nas fontes
   recuperadas, citá-las corretamente e chegar ao veredito que o conjunto de estudos
   sustenta.

Métricas:

| Métrica | O que mede |
|---|---|
| Taxa de respostas com citação válida | Fidelidade às fontes (cada consulta registra `citacoes_validas`) |
| Acurácia do veredito num conjunto de alegações com gabarito | Se a conclusão está certa |
| Latência p50 e p95 | Se a resposta chega em tempo útil (`GET /api/metricas`) |

A medição é feita por `scripts/avalia_rag.py`, e os resultados ficam em
[Avaliação](avaliacao.md). Este documento não repete números que ainda estão sendo
medidos.

### Histórico: a abordagem anterior (classificador de estilo)

Os blocos abaixo são da **abordagem anterior**, em que um classificador de risco
textual (Camada 1) decidia parte do veredito. Ficam como registro do processo. Hoje o
BERTimbau é só um sinal secundário opcional
([ADR 0009](adr/0009-bertimbau-sinal-secundario.md)). O model card atual
(`modelos/cards/bertimbau.json`, versão 2026-10-05-fbae1bb) registra F1 macro
same-source de 0,957 num teste de 70 notícias, de um treino posterior ao descrito no
bloco do BERTimbau abaixo.

**Camada 1 (anterior) — Risco textual.** Dado o texto da notícia, classificar como
desinformação ou conteúdo legítimo. Medível no MODELO: F1 por classe (nunca acurácia
isolada, por causa do desbalanceamento) e desempenho em portais não vistos no treino,
para detectar viés de fonte.

!!! info "Resultado do baseline — Fase 1 (Task 6, 2026-09-24)"
    TF-IDF (uni+bigramas) + Regressão Logística, treinado no recorte de saúde do
    Fake.br (350 notícias em 175 pares, 50/50; ver `dados/README.md`). A divisão
    treino/teste é **por par**, então a falsa e a verdadeira de um mesmo assunto
    nunca ficam em lados opostos.

    | Avaliação | F1 legítima | F1 desinformação |
    |---|---|---|
    | Teste separado (20%, 35 pares; `scripts/treina_modelo.py`) | 0,82 | 0,81 |
    | Validação cruzada por par (10 dobras), F1 macro | 0,80 ± 0,08 (mín. 0,63, máx. 0,91) | |
    | Treino só nos pares G1 → teste nos pares Estadão/Folha etc. (63 pares) | 0,78 | 0,81 |

    Matriz de confusão do teste separado (linhas = real, colunas = previsto;
    legítima, desinformação): `[[29, 6], [7, 28]]`.

    **Leitura honesta:** o número é otimista. Os termos que o modelo mais usa
    para "legítima" são `g1`, `nesta`, `feira`, `2017`, `são paulo`, marcas do
    estilo de redação do G1. Os de "desinformação" são `lula`, `dilma`,
    `petista`, `vídeo`, `você`, `eu`, do estilo do `diariodobrasil.org`, de onde
    vêm 93% das falsas. O modelo mede em boa parte **qual portal escreveu o
    texto**, não sinais de desinformação em saúde. O teste fora da fonte só varia
    as fontes das verdadeiras: as falsas continuam vindo do mesmo site. A régua
    para o BERTimbau é 0,80 de F1 macro, mas uma comparação justa exige a Onda 2
    de coleta, com fontes novas nas duas classes.

!!! info "Resultado do BERTimbau — Fase 2 (Task 10, 2026-09-27)"
    Fine-tuning de `neuralmind/bert-base-portuguese-cased` no mesmo split do
    baseline (mesmo `random_state`, mesmo agrupamento por par; ver
    `scripts/treina_bert.py`). Embeddings e as 8 primeiras das 12 camadas do
    encoder congeladas — o fine-tuning completo foi morto pelo OOM killer do
    kernel neste ambiente sem GPU.

    **F1 macro: 0,90**, contra 0,80 ± 0,08 do baseline TF-IDF — supera o
    critério de entrada da Task 10 (superar o F1 macro do baseline no
    conjunto de teste).

    **Mesma ressalva do baseline se aplica aqui:** o teste ainda vem das
    mesmas fontes de treino (93% das falsas em `diariodobrasil.org`, maioria
    das verdadeiras em `g1.globo.com`), então o ganho de 0,80 → 0,90 pode
    refletir em parte o modelo aprendendo padrões lexicais mais finos do
    mesmo viés de fonte, não necessariamente mais sinal de desinformação em
    saúde. Avaliação em portais fora do treino (Onda 2) continua pendente
    para os dois modelos.

!!! warning "Por que a abordagem anterior foi abandonada"
    A Camada 2 anterior (extração de par por dicionário, PubMed ao vivo e NLI
    zero-shot) foi lenta, cobria só 38 termos e errava em texto biomédico. E o
    classificador de estilo tinha métrica alta num dataset que não era o do problema.
    Ver [O que mudou e por quê](arquitetura.md#o-que-mudou-e-por-que).

Pergunta que conecta negócio e ML: se o sistema classificar corretamente as
afirmações, o usuário de fato entende melhor o risco e age com mais cautela antes de
repassar ou seguir a notícia? Como saberemos: via teste de compreensão nas entrevistas
(GQ3) e acompanhamento de uso real (feedback por resposta, `/api/metricas`).

## 4. Escopo em uma frase
Nosso sistema TRATA **alegações em português sobre eficácia de medicamentos e
tratamentos para doenças específicas, vindas de um link de notícia ou de um texto
colado**, comparando-as com resumos de estudos do PubMed e respondendo com um veredito
que cita as fontes, e NÃO TRATA diagnóstico individual, recomendação de tratamento
personalizado, conteúdo fora do domínio de saúde, imagens, vídeos ou áudio, nem
alegações sem estudo publicado (para as quais responde que não foi possível verificar).

## 5. Limitação declarada
O LLM que redige a resposta **pode errar mesmo com as guardas**: elas impedem citação
inexistente e afirmação sem fonte, mas não garantem que a fonte sustente a frase. A base
cobre bem só os temas do vocabulário (23 medicamentos e 15 condições); fora dele, a
qualidade depende da busca ao vivo no PubMed. A base é de resumos em inglês, não de
textos completos, e carrega o viés de publicação da literatura. O sistema depende de
cota gratuita de terceiros. Quando não há estudo sobre a alegação, ele responde **"não
foi possível verificar"**, nunca **"é falso"**: ausência de evidência não é evidência de
ausência. Não substitui orientação médica.

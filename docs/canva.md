# CANVAS — DA PERGUNTA CERTA AO OBJETIVO CERTO
Canvas de planejamento do projeto, conectando as perguntas norteadoras (guiding
questions) às atividades práticas que respondem cada uma, além dos objetivos
de negócio e de ML e do escopo do sistema.
## 1. Guiding Questions

### Dados
| # | Pergunta | Atividade | Recurso | Responsável | Prazo |
|---|----------|-----------|---------|--------------|-------|
| GQ1 | Quais fontes usaremos (PubMed, Cochrane, ANVISA, FDA, ClinicalTrials.gov) e como garantir que sejam confiáveis e atualizadas? | Mapear e testar acesso via API/scraping a cada base; definir critério de corte (revisão por pares, tipo de estudo, data). | Documentação das APIs (PubMed E-utilities, Cochrane Library, ANVISA Bulário) | Membro 1 | 24/08 |
| GQ2 | Como padronizar métricas de eficácia (taxa de resposta, NNT, redução de sintomas) que vêm em formatos diferentes entre estudos? | Coletar amostra de 15-20 artigos sobre 2-3 medicamentos e catalogar como cada um reporta eficácia. | Artigos de meta-análise já publicados como referência de padronização | Membro 2 | 31/08 |


### Usuário
| # | Pergunta | Atividade | Recurso | Responsável | Prazo |
|---|----------|-----------|---------|--------------|-------|
| GQ3 | Como o usuário formula a pergunta (medicamento + doença) e que nível de linguagem torna a resposta compreensível sem simplificar demais a ciência? | Entrevistar 5-8 pessoas leigas mostrando 2 formatos de resposta (técnico vs. simplificado) e comparar compreensão. | Roteiro de entrevista curto + protótipo de tela de resposta | Membro 3 | 27/08 |

### Modelo
| # | Pergunta | Atividade | Recurso | Responsável | Prazo |
|---|----------|-----------|---------|--------------|-------|
| GQ4 | Como agregar resultados de múltiplos estudos de forma estatisticamente responsável (meta-análise simplificada, ponderação por qualidade)? | Testar 1-2 métodos de agregação (média ponderada por tamanho de amostra/qualidade) em um caso real e comparar com meta-análise publicada do mesmo tema. | Biblioteca de meta-análise em Python (statsmodels, metafor via R) + 1 meta-análise Cochrane como gabarito | Membro 4 | 07/09 |
| GQ5 | Como evitar que o modelo "alucine" citações ou dados que não existem? | Rodar testes com prompts adversariais/casos sem evidência e verificar se o sistema inventa fontes; definir mecanismo de citação obrigatória (RAG com link à fonte original). | Conjunto de perguntas-teste com respostas conhecidas (algumas sem evidência disponível de propósito) | Membro 1 | 09/09 |


### Ética
| # | Pergunta | Atividade | Recurso | Responsável | Prazo |
|---|----------|-----------|---------|--------------|-------|
| GQ6 | Como deixar claro que o sistema não substitui orientação médica e evitar reforçar desinformação já repetida? | Desenhar o disclaimer e o fluxo de resposta para casos de "sem evidência"/"evidência contestada"; revisar com base em diretrizes de comunicação em saúde. | Guidelines de comunicação de risco em saúde (OMS, CDC) | Membro 2 | 31/08 |


### Produção
| # | Pergunta | Atividade | Recurso | Responsável | Prazo |
|---|----------|-----------|---------|--------------|-------|
| GQ7 | Como o sistema será atualizado com novos artigos e evidências ao longo do tempo? | Desenhar um pipeline simples de ingestão periódica (ex: consulta semanal à API do PubMed por medicamento cadastrado). | Estrutura de pipeline de dados (cron job / agendador + banco vetorial) | Membro 3 | 07/09 |


## 2. Objetivos do Negócio
Dor: Pessoas leem notícias sobre medicamentos e não sabem se há base científica real, podendo se automedicar ou tomar decisões de saúde com base em informação exagerada/falsa.

Objetivo de negócio: Reduzir decisões de saúde tomadas com base em notícias sem respaldo científico — medível no MUNDO (ex.: % de usuários que, após consultar o sistema, afirmam ter mudado de ideia sobre confiar/agir sobre a notícia; redução autorrelatada de intenção de automedicação).


## 3. Objetivos de ML
Objetivo de ML: Classificar a afirmação "medicamento X trata/é eficaz para a doença Y" em uma das categorias — com base científica sólida / evidência limitada ou contestada / sem evidência disponível — e estimar uma taxa de eficácia agregada quando houver dados suficientes. Medível no MODELO (ex.: F1/acurácia da classificação por categoria, calibração da taxa estimada frente a meta-análises de referência, taxa de citações verificáveis/corretas).

Pergunta que conecta os dois: se o modelo classificar corretamente 95% das afirmações, o usuário de fato entende melhor o risco e age com mais cautela antes de repassar ou seguir a notícia? Como saberemos — via teste de compreensão nas entrevistas (GQ3) e acompanhamento de uso real.

## 4. Escopo em uma frase
Nosso sistema TRATA afirmações sobre eficácia de medicamentos para doenças específicas, extraídas de notícias e conteúdos em português, comparando-as com evidências de bases científicas reconhecidas (PubMed, Cochrane, ANVISA) e NÃO TRATA diagnóstico individual, recomendação de tratamento personalizado, nem medicamentos sem estudo clínico publicado.

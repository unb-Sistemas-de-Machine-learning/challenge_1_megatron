# Guiding Questions - Megatron Challenge 1
Avaliação da base científica de tratamentos medicamentosos divulgados na mídia

## Tema
Ajudar pessoas que leram notícias sobre medicamentos a identificar se essas informações possuem base científica para o tratamento de determinadas doenças, usando dados de artigos científicos e bases de instituições confiáveis para estimar a taxa de eficácia do medicamento por condição clínica.

## Dados
- Quais fontes serão usadas (PubMed, Cochrane, ANVISA, FDA, ClinicalTrials.gov)? Como garantir que sejam confiáveis e atualizadas?
- Como extrair e padronizar informações de eficácia (ex: taxa de resposta, redução de sintomas, NNT) que vêm em formatos muito diferentes entre estudos?
- Como lidar com estudos conflitantes sobre o mesmo medicamento/doença?
- Qual o critério para incluir ou excluir um artigo (tipo de estudo, tamanho da amostra, revisão por pares, data de publicação)?
- Como representar incerteza estatística (intervalo de confiança, força da evidência) nos dados usados?

## Usuário
- Quem é o público-alvo: leigos, jornalistas, profissionais de saúde?
- Que nível de linguagem e explicação é necessário para tornar a informação compreensível sem simplificar demais a ciência?
- Como o usuário vai formular a pergunta (nome do medicamento + doença) e o que ele espera receber como resposta?
- Como evitar que o usuário interprete uma "taxa de eficácia" como garantia pessoal de resultado?
- Que tipo de feedback ou confiança o usuário precisa para agir com base na resposta (ex: procurar um médico)?

## Modelo
- O sistema vai apenas recuperar e resumir evidências (RAG) ou também vai calcular/estimar uma taxa de eficácia agregada?
- Como agregar resultados de múltiplos estudos de forma estatisticamente responsável (meta-análise simplificada, média ponderada por qualidade do estudo)?
- Como o modelo vai lidar com ausência de evidência (não é o mesmo que evidência de ineficácia)?
- Qual a métrica de avaliação do próprio modelo (precisão da classificação "com base científica" vs "sem base")?
- Como evitar alucinação de dados/citações que não existem?

## Produção
- Como o sistema será atualizado com novos artigos e evidências ao longo do tempo?
- Qual a arquitetura (pipeline de ingestão de dados, banco vetorial, API, interface)?
- Como escalar para múltiplas doenças e medicamentos sem perder qualidade na curadoria?
- Como monitorar erros ou respostas enganosas após o lançamento?

## Ética
- Como deixar claro que o sistema não substitui orientação médica?
- Como evitar reforçar desinformação já existente (ex: se uma notícia falsa for muito repetida, o sistema pode "confirmar" um viés)?
- Como tratar medicamentos controversos ou politicamente sensíveis (ex: eficácia contestada, off-label)?
- Que transparência é dada sobre as fontes e limitações da estimativa (não é 100% certeza, é uma síntese de evidências)?
- Como proteger contra uso indevido (ex: pessoas usando o sistema para justificar automedicação)?
# Verdade ou Fake?
### Checagem de alegações de saúde com evidência científica

Documentação técnica do **Challenge 1** da disciplina de Sistemas de Machine
Learning (UnB/FCTE, 2026/2) — Equipe Megatron.

## O que é este projeto?

Todo dia circulam notícias e correntes de WhatsApp sobre medicamentos "milagrosos" ou
tratamentos alternativos, muitas vezes sem respaldo científico. O usuário **cola um
link de notícia ou um texto** e recebe um veredito sobre a alegação (tem respaldo, é
contradita, é exagerada, é inconclusiva), escrito em linguagem simples e com **as fontes
citadas**: resumos de estudos do PubMed, com link para cada um.

O objetivo não é dar parecer médico, mas oferecer uma ferramenta de checagem.

!!! warning "Este sistema é apenas informativo"
    Não substitui orientação médica. As respostas são uma síntese de evidências
    publicadas, não uma prescrição. O LLM que redige a resposta pode errar mesmo com as
    guardas do sistema: confira as fontes.

## Como funciona, em resumo

1. A entrada é um link (o sistema extrai o texto da página) ou um texto colado.
2. Um LLM identifica a alegação central e a traduz para uma consulta científica.
3. Uma busca híbrida (vetorial e lexical) encontra os estudos mais próximos numa base
   de resumos do PubMed. Se a base não cobre a alegação, o sistema amplia a busca no
   PubMed na hora.
4. O LLM redige o veredito usando **apenas** esses estudos, com citações `[n]`.
5. Regras de código conferem a saída: citação inexistente é removida, afirmação sem
   citação é rebaixada, e a confiança não passa do que o tipo de estudo sustenta.
6. A resposta chega aos poucos, por streaming, e cada consulta é registrada para
   monitoramento e feedback.

Diagramas e decisões em [Arquitetura](arquitetura.md).

## Por onde começar

<div class="grid cards" markdown>

- **[Arquitetura](arquitetura.md)** — fluxo, componentes, MLOps, requisitos não funcionais e o que mudou
- **[Avaliação](avaliacao.md)** — medições do sistema
- **[API](api.md)** — endpoints e eventos de streaming
- **[Operação](operacao.md)** — subir, configurar, publicar e monitorar
- **[Dados](dados.md)** — datasheets da base de conhecimento e do corpus de treino
- **[ADRs](adr/index.md)** — decisões de arquitetura, uma por arquivo
- **[Guiding Questions](guiding-questions.md)** — perguntas norteadoras
- **[Canvas](canva.md)** — objetivos de negócio e de ML, escopo

</div>

## Limitações declaradas

- O LLM pode errar mesmo com as guardas.
- A base cobre bem só os temas do vocabulário (23 medicamentos e 15 condições); fora
  dele, o sistema depende da busca ao vivo.
- Os estudos são resumos em inglês, não textos completos, com o viés de publicação da
  literatura.
- O sistema não verifica imagens, vídeos nem áudio.
- Depende de cota gratuita de terceiros (LLM, PubMed e hospedagem).

## Base teórica

O projeto usa como referência de processo:

- Amershi et al., *Software Engineering for Machine Learning: A Case Study* (ICSE-SEIP
  2019): o fluxo de estágios de ML, a prioridade do pipeline de ponta a ponta e o dado
  como desafio central.
- Kreuzberger, Kühl e Hirschl, *Machine Learning Operations (MLOps): Overview,
  Definition, and Architecture* (IEEE Access, 2023): princípios, componentes e papéis de
  MLOps, mapeados ao projeto em [Arquitetura](arquitetura.md#mlops).
- Chip Huyen, *Projetando Sistemas de Machine Learning* (livro-base da disciplina).

## Equipe

<div align="center">
   <table style="margin-left: auto; margin-right: auto;">
        <tr>
            <td align="center">
                <a href="https://github.com/eduardoferre">
                    <img style="border-radius: 50%;" src="https://avatars.githubusercontent.com/u/67663168?v=4" width="150px;"/>
                    <h5 class="text-center">Eduardo Ferreira <br>221008632</h5>
                </a>
            </td>
            <td align="center">
                <a href="https://github.com/PedroMoraes39">
                    <img style="border-radius: 50%;" src="https://avatars.githubusercontent.com/u/78734372?v=4" width="150px;"/>
                    <h5 class="text-center">Pedro Henrique Caldeira <br>190036427</h5>
                </a>
            </td>
            <td align="center">
                <a href="https://github.com/R1K4S">
                    <img style="border-radius: 50%;" src="https://avatars.githubusercontent.com/u/135380624?v=4" width="150px;"/>
                    <h5 class="text-center">Ricardo Henrique Silva <br>231037727</h5>
                </a>
            </td>
            <td align="center">
                <a href="https://github.com/Vitorlustosa">
                    <img style="border-radius: 50%;" src="https://avatars.githubusercontent.com/u/187707438?v=4" width="150px;"/>
                    <h5 class="text-center">Vitor Guilherme <br>232014342</h5>
                </a>
            </td>
    </table>
</div>

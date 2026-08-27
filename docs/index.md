# Verdade ou Fake?
### Detecção de Desinformação em Notícias de Saúde

Documentação técnica do **Challenge 1** da disciplina de Sistemas de Machine
Learning (UnB/FCTE, 2026/2) — Equipe Megatron.

## O que é este projeto?

Todo dia circulam notícias sobre medicamentos "milagrosos" ou tratamentos
alternativos, muitas vezes sem qualquer respaldo científico. Este projeto ataca esse
problema com uma plataforma web: o usuário **cola o link de uma notícia** e recebe uma
avaliação da probabilidade de o conteúdo ser desinformação, junto com as evidências
científicas que sustentam ou contradizem a alegação.

O objetivo não é dar um veredito médico, mas oferecer uma **ferramenta de checagem** —
algo entre um *fact-checker* e um resumo de literatura científica, acessível para quem
não tem formação técnica.

!!! warning "Este sistema é apenas informativo"
    Não substitui orientação médica. As respostas são uma síntese de
    evidências disponíveis publicamente, não uma prescrição.

## Fluxo de uso

1. O usuário insere o **link da notícia** na plataforma.
2. O sistema extrai o texto limpo da página.
3. Duas camadas analisam o conteúdo **em paralelo**:
      - a **Camada 1** classifica o risco a partir de como o texto foi escrito;
      - a **Camada 2** identifica o par *medicamento + condição clínica*, consulta o PubMed e verifica se a literatura apoia a alegação.
4. Regras explícitas combinam os dois sinais em um veredito.
5. O usuário recebe a resposta com nível de confiança, fontes citadas e aviso.

## As duas camadas

| | Camada 1 | Camada 2 |
|---|---|---|
| Pergunta | *Como* a notícia foi escrita? | *O que* ela afirma? |
| Método | Classificador supervisionado (BERTimbau) | Extração de alegação + busca de evidência |
| Aprende com | Corpus rotulado de notícias PT-BR | Não é treinada — consulta bases científicas |
| Limitação | Detecta estilo, não fato | Depende de existir literatura sobre o tema |

A Camada 1 sozinha erra em alegações falsas bem redigidas — justamente o caso mais
perigoso em saúde. É por isso que a Camada 2 existe.

## Por onde começar

<div class="grid cards" markdown>

- 🏗️ **[Arquitetura](arquitetura.md)** — pipeline, stack, fases e frentes de trabalho
- 📊 **[Fontes de Dados](dados.md)** — datasets, bases científicas, riscos e governança
- ❓ **[Guiding Questions](guiding-questions.md)** — perguntas norteadoras
- 🗺️ **[Canvas](canva.md)** — objetivos de negócio e de ML, escopo, cronograma

</div>

## Base teórica

O projeto usa como referência de processo o artigo **Amershi et al., *Software
Engineering for Machine Learning: A Case Study*** (ICSE-SEIP 2019), em especial:

- o **fluxo de nove estágios** de ML e seus laços de realimentação (Figura 1);
- a prioridade de **pipeline end-to-end** antes de otimizar etapas isoladas (Seção V-A);
- o tratamento de **dados como o desafio nº 1** em qualquer nível de maturidade (Tabela II);
- o **versionamento e proveniência de dados** como diferença fundamental frente à engenharia de software tradicional (Seção VII-A).

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

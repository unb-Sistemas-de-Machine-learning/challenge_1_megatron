# Verdade ou Fake?
### Evidência Científica de Tratamentos Medicamentosos

Documentação técnica do **Challenge 1** da disciplina de Sistemas de Machine
Learning (UnB/FCTE, 2026/2) — Equipe Megatron.

## O que é este projeto?

Todo dia circulam notícias sobre medicamentos "milagrosos" ou tratamentos
alternativos, muitas vezes sem qualquer respaldo científico. Este projeto
nasce para atacar esse problema: dado um **medicamento** e uma **doença**,
o sistema busca evidências em bases científicas confiáveis e retorna uma
estimativa da **taxa de eficácia**, com nível de confiança e fontes citadas.

O objetivo não é dar um veredito médico, mas dar à pessoa uma **ferramenta de
checagem** — algo entre um fact-checker e um resumo de literatura científica,
acessível para quem não tem formação técnica.

!!! warning "Este sistema é apenas informativo"
    Não substitui orientação médica. As respostas são uma síntese de
    evidências disponíveis publicamente, não uma prescrição.

## Fontes de dados

O sistema consulta bases de instituições reconhecidas:

- **PubMed** — literatura biomédica revisada por pares
- **Cochrane** — revisões sistemáticas e meta-análises
- **ANVISA** — regulação de medicamentos no Brasil
- **FDA** — regulação de medicamentos nos EUA
- **ClinicalTrials.gov** — registro de ensaios clínicos

## Fluxo de uso

1. O usuário informa o **medicamento** e a **doença**.
2. O sistema busca evidências científicas relacionadas nas bases acima.
3. As evidências são sintetizadas, com nível de confiança e citação das fontes.
4. O usuário recebe uma resposta clara sobre o que a ciência já sabe (ou não sabe) a respeito.

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

# Verdade ou Fake? — Detecção de Desinformação em Notícias de Saúde
**Challenge 1** - Equipe Megatron - Sistemas de Machine Learning 2026/02

📖 **[Documentação completa](https://unb-sistemas-de-machine-learning.github.io/challenge_1_megatron/)**

## Tema
Plataforma web onde o usuário **cola o link de uma notícia** sobre saúde e recebe uma
avaliação da probabilidade de o conteúdo ser falso ou enganoso, acompanhada das
evidências científicas que sustentam ou contradizem a alegação.

O escopo é restrito a **medicamentos, tratamentos e terapias** — não cobre saúde em
geral, diagnóstico individual nem recomendação personalizada.

## Como funciona

```
🔗 link → [0] extrai texto → ┬→ [1] Camada 1: risco textual (ML) ──┐
                            │                                     ├→ [3] fusão → veredito
                            └→ [2] Camada 2: evidência científica ─┘   + confiança
                                                                      + fontes
```

Duas camadas independentes analisam a notícia, e regras explícitas combinam os
resultados:

- **Camada 1 — Risco textual.** Classificador supervisionado treinado em corpus rotulado de notícias em português. Detecta padrões de escrita típicos de desinformação.
- **Camada 2 — Verificação por evidência.** Extrai o par *medicamento + condição clínica* do texto, consulta o PubMed e classifica se a literatura apoia, contradiz ou não cobre a alegação.

**Por que duas camadas.** A Camada 1 sozinha aprende *estilo*, não *fato* — ela erra em
alegações falsas bem escritas, justamente o caso mais perigoso em saúde. A Camada 2
existe para cobrir essa lacuna. Detalhes em [Arquitetura](docs/arquitetura.md).

## Stack

Python 3.11 · scikit-learn · Hugging Face Transformers (BERTimbau) · trafilatura ·
PubMed E-utilities · Streamlit · MkDocs

**Orçamento zero:** nenhum componente do sistema depende de API paga.

## Fontes de dados

| Finalidade | Fontes |
|---|---|
| Treino da Camada 1 | Fake.br Corpus, FakeRecogna (recorte de saúde) + coleta em agências de checagem BR |
| Consulta da Camada 2 | PubMed, DeCS/MeSH, DCB/ANVISA, Cochrane, ClinicalTrials.gov |

Levantamento completo e limitações em [Fontes de Dados](docs/dados.md).

## Documentação

| Documento | Conteúdo |
|---|---|
| [Arquitetura](docs/arquitetura.md) | Pipeline, stack, fases e frentes de trabalho |
| [Fontes de Dados](docs/dados.md) | Datasets, bases científicas, riscos e governança |
| [Guiding Questions](docs/guiding-questions.md) | Perguntas norteadoras do projeto |
| [Canvas](docs/canva.md) | Objetivos de negócio e de ML, escopo, cronograma |

## Aviso
Este sistema é apenas informativo e **não substitui orientação médica**. As respostas
são uma síntese de evidências públicas, não uma prescrição.

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

## Disciplina

Sistemas de Machine Learning — UnB/FCTE — Profs. Isaque Alves e Guilherme Fernandes — 2026/2

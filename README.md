# Verdade ou Fake? — Detecção de Desinformação em Notícias de Saúde
**Challenge 1** - Equipe Megatron - Sistemas de Machine Learning 2026/02

📖 **[Documentação completa](https://unb-sistemas-de-machine-learning.github.io/challenge_1_megatron/)**

🚀 **[Demo ao vivo](https://pregnancy-provide-sterling-behind.trycloudflare.com/)** — app rodando no Google Colab
(`notebooks/app_colab.ipynb`). O link é um túnel temporário do Cloudflare: só funciona enquanto a
sessão do Colab estiver aberta e muda a cada nova execução.

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
PubMed E-utilities · Streamlit · Docker · Hugging Face Spaces · MkDocs

**Orçamento zero:** nenhum componente do sistema depende de API paga.

## Como rodar

```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt --extra-index-url https://download.pytorch.org/whl/cpu

python scripts/prepara_dataset.py       # gera o recorte de saúde (Fake.br)
python scripts/prepara_fakerecogna.py   # opcional: 2ª fonte (FakeRecogna) — demorado, milhares de requisições
python scripts/treina_modelo.py         # baseline TF-IDF (referência de comparação) + modelos/cards/baseline.json
python scripts/treina_bert.py           # BERTimbau (classificador em produção) + modelos/cards/bertimbau.json
python scripts/verifica_gate.py modelos/cards/bertimbau.json   # confere o gate de qualidade

streamlit run app.py                    # abre a interface

pytest                                  # roda os testes
pytest -m "not rede"                    # roda os testes sem tocar a rede (CI offline)
```

O app serve o **BERTimbau** (F1 macro 0,96 contra 0,80 do baseline TF-IDF) e só
o carrega se o model card `modelos/cards/bertimbau.json` estiver em
`"status": "producao"` **e** o hash dos pesos bater com o registrado no card.
`treina_bert.py` sempre gera o card em `staging`: depois de revisar as métricas,
mude o status para `producao` à mão — a promoção é uma decisão humana
deliberada, não automática. Para regenerar o card de um modelo já treinado sem
retreinar: `python scripts/treina_bert.py --somente-avaliar`.

A Camada 2c usa o modelo de NLI **zero-shot**
(`MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`), baixado do Hub.
O fine-tuning experimental (`scripts/treina_suporte.py` → `modelos/suporte_finetuned/`)
não é usado em produção: foi treinado com só 79 pares anotados e não tem
avaliação que justifique substituir o zero-shot.

## Deploy

O app é publicado num **Hugging Face Space** (SDK Docker, CPU gratuito — o
Streamlit Community Cloud não comporta os ~1,5 GB de RAM dos dois modelos). Os
pesos do BERTimbau não vão para o git; ficam num repositório de modelo do Hub
e são baixados na inicialização.

1. **Publicar o modelo** (uma vez por retreino), após `hf auth login`:
   ```bash
   python scripts/publica_modelo.py <usuario>/bertimbau-saude [--privado]
   ```
   O script confere que os pesos batem com o card e imprime o commit publicado.
2. **Promover o card** `modelos/cards/bertimbau.json` a `"status": "producao"`
   e fazer commit.
3. **Configurar o Space** (Settings → Variables and secrets):

   | Nome | Tipo | Valor |
   |---|---|---|
   | `VOF_MODELO_RISCO` | variável | `<usuario>/bertimbau-saude` |
   | `VOF_MODELO_RISCO_REVISAO` | variável | commit impresso no passo 1 (fixa a versão) |
   | `HF_TOKEN` | secret | token de leitura — só se o repo do modelo for privado |
   | `NCBI_API_KEY` | secret | chave gratuita do NCBI (sobe o limite do PubMed de 3 para 10 req/s) |
   | `NCBI_EMAIL` | variável | e-mail de contato da equipe, pedido pelo NCBI |

4. **Publicar o app**: automático a cada push na `main` pelo workflow
   `deploy-app.yml` (configure a variável `HF_SPACE` e o secret `HF_TOKEN` com
   escrita no GitHub), ou manualmente com
   `python scripts/publica_space.py <usuario>/verdade-ou-fake`. Os dois caminhos
   se recusam a publicar se o card não estiver em `producao`.

Para rodar a mesma imagem localmente:

```bash
docker build -t verdade-ou-fake .
docker run -p 8501:8501 -e VOF_MODELO_RISCO=<usuario>/bertimbau-saude verdade-ou-fake
```

**Segurança.** O servidor só baixa links `http(s)` que resolvem para IPs
públicos — inclusive em cada redirecionamento — e recusa páginas acima de
5 MB, para não servir de ponte para a rede interna (SSRF).

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

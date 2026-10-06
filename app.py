"""Interface web do Verdade ou Fake.

Uso: streamlit run app.py

Variáveis de ambiente (todas opcionais em desenvolvimento):
    VOF_MODELO_RISCO          diretório local ou repo do Hugging Face Hub com o
                              BERTimbau (padrão: modelos/bertimbau)
    VOF_MODELO_RISCO_REVISAO  branch, tag ou commit do repo no Hub
    HF_TOKEN                  token de leitura, se o repo do Hub for privado
    NCBI_API_KEY, NCBI_EMAIL  identificação no PubMed (ver evidencia.py)
"""

import os
import sys
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.classificador import construir_modelo_bert, prever_risco_bert
from verdade_ou_fake.ingestao import UrlNaoPermitida, validar_url
from verdade_ou_fake.modelo_producao import ModeloIndisponivel, preparar_modelo_de_producao
from verdade_ou_fake.pipeline import analisar_link
from verdade_ou_fake.suporte import carregar_modelo_nli
from verdade_ou_fake.vocabulario import carregar_vocabulario

# BERTimbau (Task 10, Fase 2) substitui o baseline TF-IDF: F1 macro 0,96 contra
# 0,80 do baseline — métricas e hash em modelos/cards/bertimbau.json.
ORIGEM_MODELO = os.environ.get("VOF_MODELO_RISCO", str(RAIZ / "modelos" / "bertimbau"))
REVISAO_MODELO = os.environ.get("VOF_MODELO_RISCO_REVISAO") or None
CAMINHO_CARD = RAIZ / "modelos" / "cards" / "bertimbau.json"
CAMINHO_VOCABULARIO = RAIZ / "dados" / "vocabulario_seed.csv"
TAMANHO_MAXIMO_TOKENS_BERT = 256  # mesmo truncamento usado no treino

SELOS_SUPORTE = {
    "apoia": "✅ Apoia a alegação",
    "contradiz": "❌ Contradiz a alegação",
    "nao_determinado": "❔ Não determinado",
    "nao_avaliado": "",
}


@st.cache_resource(show_spinner="Carregando os modelos (só na primeira vez)...")
def carregar_recursos():
    """Carrega modelos e vocabulário uma única vez por processo.

    O BERTimbau só é carregado se o model card estiver em produção e o hash
    dos pesos bater. O NLI da Camada 2c é pré-carregado aqui para que o
    primeiro usuário não pague o download dele no meio da análise.
    """
    diretorio = preparar_modelo_de_producao(ORIGEM_MODELO, CAMINHO_CARD, revisao=REVISAO_MODELO)
    modelo, tokenizer = construir_modelo_bert(str(diretorio))
    carregar_modelo_nli()
    return modelo, tokenizer, carregar_vocabulario(CAMINHO_VOCABULARIO)


st.set_page_config(page_title="Verdade ou Fake?", page_icon="🔍")

st.title("🔍 Verdade ou Fake?")
st.caption("Checagem de notícias sobre medicamentos e tratamentos")

st.warning(
    "**Este sistema é apenas informativo e não substitui orientação médica.** "
    "As respostas são uma síntese de evidências públicas, não uma prescrição."
)

try:
    modelo, tokenizer, vocabulario = carregar_recursos()
except ModeloIndisponivel as erro:
    st.error(f"O classificador de risco não pode ser servido: {erro}")
    st.stop()

url = st.text_input(
    "Cole o link da notícia",
    placeholder="https://portal.exemplo.com/saude/materia",
)

url = url.strip()
analisar = st.button("Analisar", type="primary") and url
if analisar:
    try:
        validar_url(url)
    except UrlNaoPermitida as erro:
        st.error(f"Link não aceito: {erro}")
        analisar = False

if analisar:
    with st.spinner("Extraindo o texto e consultando a literatura científica..."):
        veredito = analisar_link(
            url,
            modelo=None,
            vocabulario=vocabulario,
            calcular_risco=lambda texto: prever_risco_bert(
                texto, modelo, tokenizer, TAMANHO_MAXIMO_TOKENS_BERT
            ),
        )

    if veredito is None:
        st.error(
            "Não conseguimos extrair o texto dessa página. Ela pode estar atrás de "
            "paywall, exigir login, ou usar um formato que ainda não suportamos."
        )
    else:
        st.subheader(f"{veredito.icone} {veredito.rotulo}")
        st.write(veredito.explicacao)

        col_a, col_b = st.columns(2)
        col_a.metric("Risco pelo texto", f"{veredito.risco_textual:.0%}")
        col_b.metric("Confiança do veredito", veredito.confianca.capitalize())

        if veredito.alegacao:
            st.info(
                f"**Alegação identificada:** {veredito.alegacao.medicamento_pt} "
                f"→ {veredito.alegacao.condicao_pt}"
            )

        if veredito.evidencia and veredito.evidencia.artigos:
            st.subheader("Fontes científicas encontradas")
            st.caption(
                "Cada artigo foi lido por um modelo de linguagem (NLI) para decidir "
                "se ele apoia ou contradiz a alegação — não é só uma lista de resultados de busca."
            )
            for artigo in veredito.evidencia.artigos:
                tipos = ", ".join(artigo.tipos_estudo) or "não classificado"
                selo = SELOS_SUPORTE.get(artigo.suporte, "")
                st.markdown(
                    f"- [{artigo.titulo}](https://pubmed.ncbi.nlm.nih.gov/{artigo.pmid}/)  \n"
                    f"  <sub>{tipos} · {artigo.ano or 's/d'} · PMID {artigo.pmid}"
                    + (f" · {selo}" if selo else "")
                    + "</sub>",
                    unsafe_allow_html=True,
                )

        with st.expander("Como interpretar este resultado"):
            st.markdown(
                """
                O sistema tem **duas camadas** e nenhuma delas dá veredito médico:

                - **Risco pelo texto** vem de um modelo que aprendeu padrões de
                  escrita típicos de desinformação. Ele avalia *como* a notícia foi
                  escrita, não se o que ela afirma é verdade.
                - **Fontes científicas** vêm de uma busca no PubMed pelo par
                  medicamento + condição encontrado no texto. Cada resumo encontrado
                  passa por um modelo de inferência textual (NLI) que decide se ele
                  **apoia** ou **contradiz** a alegação — o selo ao lado de cada
                  artigo mostra esse veredito.

                Quando não encontramos literatura, respondemos *"não foi possível
                verificar"* — nunca *"é falso"*. Ausência de estudos não é prova de
                ineficácia.
                """
            )
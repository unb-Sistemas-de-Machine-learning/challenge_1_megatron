"""Interface web do Verdade ou Fake.

Uso: streamlit run app.py
"""

import sys
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.classificador import construir_modelo_bert, prever_risco_bert
from verdade_ou_fake.pipeline import analisar_link
from verdade_ou_fake.vocabulario import carregar_vocabulario

# BERTimbau (Task 10, Fase 2) substitui o baseline TF-IDF: F1 macro medido de
# 0,90 contra 0,80 do baseline em scripts/treina_bert.py — ver docs/canva.md.
CAMINHO_MODELO = RAIZ / "modelos" / "bertimbau"
CAMINHO_VOCABULARIO = RAIZ / "dados" / "vocabulario_seed.csv"
TAMANHO_MAXIMO_TOKENS_BERT = 256  # mesmo truncamento usado no treino

CORES = {"alta": "🟢", "media": "🟡", "baixa": "⚪"}

SELOS_SUPORTE = {
    "apoia": "✅ Apoia a alegação",
    "contradiz": "❌ Contradiz a alegação",
    "nao_determinado": "❔ Não determinado",
    "nao_avaliado": "",
}


@st.cache_resource
def carregar_recursos():
    """Carrega modelo, tokenizer e vocabulário uma única vez por sessão."""
    modelo, tokenizer = construir_modelo_bert(str(CAMINHO_MODELO))
    return modelo, tokenizer, carregar_vocabulario(CAMINHO_VOCABULARIO)


st.set_page_config(page_title="Verdade ou Fake?", page_icon="🔍")

st.title("🔍 Verdade ou Fake?")
st.caption("Checagem de notícias sobre medicamentos e tratamentos")

st.warning(
    "**Este sistema é apenas informativo e não substitui orientação médica.** "
    "As respostas são uma síntese de evidências públicas, não uma prescrição."
)

if not (CAMINHO_MODELO / "config.json").exists():
    st.error(
        f"Modelo não encontrado em `{CAMINHO_MODELO}`. "
        "Rode `python scripts/treina_bert.py` antes de iniciar a interface."
    )
    st.stop()

modelo, tokenizer, vocabulario = carregar_recursos()

url = st.text_input(
    "Cole o link da notícia",
    placeholder="https://portal.exemplo.com/saude/materia",
)

if st.button("Analisar", type="primary") and url:
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
        st.subheader(f"{CORES[veredito.confianca]} {veredito.rotulo}")
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

"""Interface web do Verdade ou Fake.

Uso: streamlit run app.py
"""

import sys
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).parent
sys.path.insert(0, str(RAIZ / "src"))

from verdade_ou_fake.classificador import carregar
from verdade_ou_fake.pipeline import analisar_link
from verdade_ou_fake.vocabulario import carregar_vocabulario

CAMINHO_MODELO = RAIZ / "modelos" / "baseline.joblib"
CAMINHO_VOCABULARIO = RAIZ / "dados" / "vocabulario_seed.csv"

CORES = {"alta": "🟢", "media": "🟡", "baixa": "⚪"}


@st.cache_resource
def carregar_recursos():
    """Carrega modelo e vocabulário uma única vez por sessão."""
    return carregar(CAMINHO_MODELO), carregar_vocabulario(CAMINHO_VOCABULARIO)


st.set_page_config(page_title="Verdade ou Fake?", page_icon="🔍")

st.title("🔍 Verdade ou Fake?")
st.caption("Checagem de notícias sobre medicamentos e tratamentos")

st.warning(
    "**Este sistema é apenas informativo e não substitui orientação médica.** "
    "As respostas são uma síntese de evidências públicas, não uma prescrição."
)

if not CAMINHO_MODELO.exists():
    st.error(
        f"Modelo não encontrado em `{CAMINHO_MODELO}`. "
        "Rode `python scripts/treina_modelo.py` antes de iniciar a interface."
    )
    st.stop()

modelo, vocabulario = carregar_recursos()

url = st.text_input(
    "Cole o link da notícia",
    placeholder="https://portal.exemplo.com/saude/materia",
)

if st.button("Analisar", type="primary") and url:
    with st.spinner("Extraindo o texto e consultando a literatura científica..."):
        veredito = analisar_link(url, modelo, vocabulario)

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
            for artigo in veredito.evidencia.artigos:
                tipos = ", ".join(artigo.tipos_estudo) or "não classificado"
                st.markdown(
                    f"- [{artigo.titulo}](https://pubmed.ncbi.nlm.nih.gov/{artigo.pmid}/)  \n"
                    f"  <sub>{tipos} · {artigo.ano or 's/d'} · PMID {artigo.pmid}</sub>",
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
                  medicamento + condição encontrado no texto.

                Quando não encontramos literatura, respondemos *"não foi possível
                verificar"* — nunca *"é falso"*. Ausência de estudos não é prova de
                ineficácia.
                """
            )

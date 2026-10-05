"""Etapa [2c] — decide se a literatura apoia ou contradiz a alegação.

A Camada 2 da PoC (Fase 1) só respondia "encontrou literatura" ou "não
cobre" — ela nunca lia o conteúdo do resumo para julgar se ele sustenta ou
nega a alegação da notícia. Esse módulo fecha essa lacuna com um modelo de
NLI (Natural Language Inference) zero-shot: sem fine-tuning, aproveitando um
modelo multilíngue já treinado para inferência textual.

Mesma divisão das demais etapas: a decisão (rótulo + limiar de confiança) é
pura e testada; `classificar_suporte` recebe o classificador via injeção de
dependência (mesmo padrão do `buscar` em `pipeline.py`) para que os testes
rodem sem carregar o modelo nem tocar a rede.
"""

from collections.abc import Callable
from dataclasses import replace

from verdade_ou_fake.tipos import Alegacao, Evidencia

MODELO_NLI = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"

# Abaixo disso, o modelo não está confiante o bastante para afirmar apoio ou
# contradição — devolver "nao_determinado" é mais honesto que arriscar.
#
# Calibrado empiricamente em 79 pares reais do PubMed anotados manualmente
# (dados/avaliacao/suporte_pubmed.json, ver scripts/avalia_suporte.py): no
# limiar original de 0,65 o modelo confundia 73% dos casos realmente
# ambíguos com apoio/contradição decisivos. Subir demais o limiar (0,90+)
# "resolve" isso só porque a maioria dos casos é ambígua — o modelo passa a
# responder "não determinado" quase sempre e para de identificar
# apoio/contradição de verdade (recall de contradição cai a 0%). 0,75 é o
# ponto em que o recall de apoio/contradição ainda se mantém e o de
# "não determinado" já melhora bastante (27% -> 44%).
LIMIAR_CONFIANCA = 0.75

# sequencia, rotulos -> {"labels": [...], "scores": [...]} (ordenados por score desc.)
ClassificadorNLI = Callable[[str, list[str]], dict]

_pipeline_nli = None


def carregar_modelo_nli():
    """Carrega (uma vez por processo) o pipeline zero-shot de NLI.

    O app chama isso na inicialização para que o download e a carga do
    modelo (~560 MB) não caiam na primeira análise de um usuário.
    """
    global _pipeline_nli
    if _pipeline_nli is None:
        from transformers import pipeline

        _pipeline_nli = pipeline("zero-shot-classification", model=MODELO_NLI)
    return _pipeline_nli


def _classificar_com_modelo_padrao(sequencia: str, rotulos: list[str]) -> dict:
    """Casca de I/O: carrega o pipeline zero-shot (uma vez) e classifica.

    Os testes nunca chegam aqui porque sempre injetam um `classificador` falso.
    """
    return carregar_modelo_nli()(sequencia, candidate_labels=rotulos)


def _interpretar_resultado(rotulo_vencedor: str, score: float) -> str:
    """Traduz o rótulo e a confiança do modelo em apoia/contradiz/nao_determinado."""
    if score < LIMIAR_CONFIANCA:
        return "nao_determinado"
    return "contradiz" if "contradiz" in rotulo_vencedor else "apoia"


def classificar_suporte(
    resumo: str,
    alegacao: str,
    classificador: ClassificadorNLI = _classificar_com_modelo_padrao,
) -> str:
    """Classifica a relação entre o resumo do artigo e a alegação da notícia.

    A alegação entra no texto dos rótulos candidatos — sem isso o modelo
    julgaria apenas o tom do resumo, não se ele sustenta ESSA alegação
    específica.
    """
    # Alguns registros do PubMed não têm resumo (cartas, anais de congresso).
    # Sem texto não há o que classificar — mandar string vazia ao modelo
    # derruba o pipeline zero-shot.
    if not resumo.strip():
        return "nao_determinado"

    rotulos = [
        f"apoia a alegação de que {alegacao}",
        f"contradiz a alegação de que {alegacao}",
    ]
    resultado = classificador(resumo, rotulos)
    return _interpretar_resultado(resultado["labels"][0], resultado["scores"][0])


def _texto_da_alegacao(alegacao: Alegacao) -> str:
    """Frase em português usada como hipótese na classificação de suporte."""
    return f"{alegacao.medicamento_pt} trata {alegacao.condicao_pt}"


def _agregar_suporte(rotulos_dos_artigos: list[str]) -> str:
    """Combina o suporte de cada artigo num veredito único para a evidência.

    Apoio e contradição juntos viram "conflitante" — informar isso ao usuário
    é mais honesto que escolher um lado. "nao_determinado" só aparece quando
    nenhum artigo teve confiança suficiente para apoiar ou contradizer.
    """
    tem_apoio = "apoia" in rotulos_dos_artigos
    tem_contradicao = "contradiz" in rotulos_dos_artigos

    if tem_apoio and tem_contradicao:
        return "conflitante"
    if tem_apoio:
        return "apoia"
    if tem_contradicao:
        return "contradiz"
    return "nao_determinado"


# resumo, texto_da_alegacao -> "apoia" | "contradiz" | "nao_determinado"
ClassificadorDeSuporte = Callable[[str, str], str]


def avaliar_evidencia(
    alegacao: Alegacao,
    evidencia: Evidencia,
    classificar: ClassificadorDeSuporte = classificar_suporte,
) -> Evidencia:
    """Classifica o suporte de cada artigo da evidência e agrega o resultado.

    Sem artigos não há o que classificar — devolve a evidência como veio, com
    suporte "nao_avaliado". Não modifica `evidencia` nem seus artigos; devolve
    cópias novas (mesmo padrão imutável das demais etapas).
    """
    if not evidencia.artigos:
        return evidencia

    texto_alegacao = _texto_da_alegacao(alegacao)
    artigos_avaliados = [
        replace(artigo, suporte=classificar(artigo.resumo, texto_alegacao))
        for artigo in evidencia.artigos
    ]
    suporte_agregado = _agregar_suporte([artigo.suporte for artigo in artigos_avaliados])

    return replace(evidencia, artigos=artigos_avaliados, suporte=suporte_agregado)

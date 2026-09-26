"""Etapa [3] — combina o sinal das duas camadas em um veredito.

Regras explícitas, não um modelo treinado. Duas razões: não existe dado
rotulado para supervisionar a fusão, e regras são auditáveis — o usuário
consegue ver por que recebeu aquele resultado.

Princípio inegociável: ausência de evidência NUNCA vira "é falso".
"""

from verdade_ou_fake.tipos import Alegacao, Evidencia, Veredito

LIMIAR_RISCO_ALTO = 0.6

AVISO = "Este resultado é informativo e não substitui orientação médica."


def fundir(
    risco_textual: float,
    alegacao: Alegacao | None,
    evidencia: Evidencia | None,
) -> Veredito:
    """Aplica a tabela de decisão descrita em docs/arquitetura.md."""
    risco_alto = risco_textual >= LIMIAR_RISCO_ALTO

    if alegacao is None or evidencia is None:
        complemento = (
            " O texto apresenta sinais de alerta na forma de escrita."
            if risco_alto
            else " O texto não apresenta sinais de alerta evidentes."
        )
        return Veredito(
            rotulo="Não foi possível verificar",
            confianca="baixa",
            risco_textual=risco_textual,
            alegacao=alegacao,
            evidencia=evidencia,
            explicacao=(
                "Não identificamos um par medicamento + condição clínica no texto, "
                "então não houve o que consultar na literatura científica."
                + complemento
                + " "
                + AVISO
            ),
        )

    if evidencia.cobertura == "nao_cobre":
        return Veredito(
            rotulo="Não foi possível verificar",
            confianca="baixa",
            risco_textual=risco_textual,
            alegacao=alegacao,
            evidencia=evidencia,
            explicacao=(
                f"Não encontramos literatura no PubMed sobre {alegacao.medicamento_pt} "
                f"para {alegacao.condicao_pt}. Ausência de estudos não significa que a "
                "afirmação seja falsa — pode apenas não ter sido pesquisada ainda. "
                + AVISO
            ),
        )

    if evidencia.forca == "fraca":
        return Veredito(
            rotulo="Literatura limitada sobre o tema",
            confianca="baixa",
            risco_textual=risco_textual,
            alegacao=alegacao,
            evidencia=evidencia,
            explicacao=(
                f"Encontramos estudos sobre {alegacao.medicamento_pt} e "
                f"{alegacao.condicao_pt}, mas de tipos que oferecem evidência fraca "
                "(relatos de caso, estudos preliminares). " + AVISO
            ),
        )

    if risco_alto:
        return Veredito(
            rotulo="Existe literatura, mas o texto tem sinais de alerta",
            confianca="media",
            risco_textual=risco_textual,
            alegacao=alegacao,
            evidencia=evidencia,
            explicacao=(
                f"Há estudos sobre {alegacao.medicamento_pt} e {alegacao.condicao_pt}, "
                "mas a forma como a notícia foi escrita tem características associadas "
                "a desinformação. Vale conferir as fontes originais abaixo. " + AVISO
            ),
        )

    return Veredito(
        rotulo="Tema com respaldo na literatura",
        confianca="media",
        risco_textual=risco_textual,
        alegacao=alegacao,
        evidencia=evidencia,
        explicacao=(
            f"Existem estudos de boa qualidade sobre {alegacao.medicamento_pt} e "
            f"{alegacao.condicao_pt}. Isso indica que o tema é pesquisado, não que a "
            "afirmação específica da notícia esteja correta. " + AVISO
        ),
    )

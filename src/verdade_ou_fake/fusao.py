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

    # Etapa [2c]: quando a Camada 2 leu os resumos e decidiu apoia/contradiz com
    # confiança, esse sinal fala mais alto que a mera presença de estudos —
    # é o que diferencia "existe literatura" de "a literatura diz isto".
    if evidencia.suporte == "contradiz":
        return Veredito(
            rotulo="Literatura contradiz a alegação",
            confianca="alta" if evidencia.forca in ("forte", "moderada") else "media",
            risco_textual=risco_textual,
            alegacao=alegacao,
            evidencia=evidencia,
            explicacao=(
                f"Os artigos que encontramos sobre {alegacao.medicamento_pt} e "
                f"{alegacao.condicao_pt} contradizem a alegação da notícia — eles não "
                "confirmam o efeito descrito. Vale conferir as fontes originais "
                "abaixo. " + AVISO
            ),
        )

    if evidencia.suporte == "conflitante":
        return Veredito(
            rotulo="Literatura tem resultados conflitantes sobre o tema",
            confianca="baixa",
            risco_textual=risco_textual,
            alegacao=alegacao,
            evidencia=evidencia,
            explicacao=(
                f"Encontramos estudos sobre {alegacao.medicamento_pt} e "
                f"{alegacao.condicao_pt} que apontam em direções diferentes — alguns "
                "apoiam a alegação, outros a contradizem. O tema ainda não tem "
                "consenso na literatura. " + AVISO
            ),
        )

    # Evidência fraca com suporte="apoia" é o par simétrico do contradiz+fraca
    # acima: sem este caso, o sinal da Camada 2c (que o NLI leu e decidiu que os
    # resumos apoiam a alegação) desaparecia silenciosamente dentro do rótulo
    # genérico "Literatura limitada" — o usuário nunca saberia que os poucos
    # estudos fracos encontrados ao menos apontavam a favor.
    if evidencia.forca == "fraca" and evidencia.suporte == "apoia":
        return Veredito(
            rotulo="Literatura aponta a favor, mas é limitada",
            confianca="baixa",
            risco_textual=risco_textual,
            alegacao=alegacao,
            evidencia=evidencia,
            explicacao=(
                f"Encontramos estudos sobre {alegacao.medicamento_pt} e "
                f"{alegacao.condicao_pt} que apontam a favor da alegação, mas são de "
                "tipos que oferecem evidência fraca (relatos de caso, estudos "
                "preliminares) — vale cautela antes de considerar isso uma "
                "confirmação. " + AVISO
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

    if evidencia.suporte == "apoia":
        return Veredito(
            rotulo="Literatura apoia a alegação",
            confianca="alta",
            risco_textual=risco_textual,
            alegacao=alegacao,
            evidencia=evidencia,
            explicacao=(
                f"Os artigos que encontramos sobre {alegacao.medicamento_pt} e "
                f"{alegacao.condicao_pt} apoiam a alegação da notícia. Isso não prova "
                "que o caso específico relatado é verdadeiro, mas indica respaldo "
                "científico para a relação entre eles. " + AVISO
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
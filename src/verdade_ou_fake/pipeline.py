"""Costura as quatro etapas do sistema.

Este módulo não tem regra de negócio própria — ele só ordena as chamadas. Toda
decisão está nos módulos das etapas.
"""

from collections.abc import Callable

from sklearn.pipeline import Pipeline as ModeloSklearn

from verdade_ou_fake.classificador import prever_risco
from verdade_ou_fake.evidencia import buscar_evidencia
from verdade_ou_fake.fusao import fundir
from verdade_ou_fake.ingestao import extrair_noticia
from verdade_ou_fake.tipos import Alegacao, Evidencia, Veredito
from verdade_ou_fake.vocabulario import extrair_alegacao

BuscadorDeEvidencia = Callable[[Alegacao], Evidencia]


def analisar_texto(
    texto: str,
    modelo: ModeloSklearn,
    vocabulario: dict[str, list[tuple[str, str]]],
    buscar: BuscadorDeEvidencia = buscar_evidencia,
) -> Veredito:
    """Roda as etapas [1], [2] e [3] sobre um texto já extraído.

    `buscar` é injetável para que os testes rodem sem tocar a rede.
    """
    risco = prever_risco(modelo, texto)
    alegacao = extrair_alegacao(texto, vocabulario)

    # Sem o par medicamento+condição não há query a fazer — pular a busca
    # evita requisição inútil a uma API pública gratuita.
    evidencia = buscar(alegacao) if alegacao is not None else None

    return fundir(risco_textual=risco, alegacao=alegacao, evidencia=evidencia)


def analisar_link(
    url: str,
    modelo: ModeloSklearn,
    vocabulario: dict[str, list[tuple[str, str]]],
) -> Veredito | None:
    """Fluxo completo, da etapa [0] à [3]. Devolve None se a extração falhar."""
    noticia = extrair_noticia(url)
    if noticia is None:
        return None

    texto_completo = f"{noticia.titulo}\n\n{noticia.texto}"
    return analisar_texto(texto_completo, modelo, vocabulario)

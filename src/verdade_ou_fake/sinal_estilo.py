import logging
import os
from collections.abc import Callable
from pathlib import Path

from verdade_ou_fake.config import RAIZ

TAMANHO_MAXIMO_TOKENS = 256
registro = logging.getLogger(__name__)


def carregar() -> Callable[[str], float] | None:
    origem = os.environ.get("VOF_MODELO_RISCO", str(RAIZ / "modelos" / "bertimbau"))
    if "/" not in origem.strip("./") and not Path(origem).is_dir():
        return None
    if not Path(origem).is_dir() and "VOF_MODELO_RISCO" not in os.environ:
        return None
    try:
        from verdade_ou_fake.classificador import construir_modelo_bert, prever_risco_bert
        from verdade_ou_fake.modelo_producao import preparar_modelo_de_producao

        diretorio = preparar_modelo_de_producao(
            origem,
            RAIZ / "modelos" / "cards" / "bertimbau.json",
            revisao=os.environ.get("VOF_MODELO_RISCO_REVISAO") or None,
        )
        modelo, tokenizer = construir_modelo_bert(str(diretorio))
    except Exception as erro:
        registro.warning("Sinal de estilo desativado: %s", erro)
        return None
    return lambda texto: float(prever_risco_bert(texto, modelo, tokenizer, TAMANHO_MAXIMO_TOKENS))

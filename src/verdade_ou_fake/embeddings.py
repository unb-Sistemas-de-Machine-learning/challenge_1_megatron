import threading
from collections.abc import Callable

import numpy as np

Embutidor = Callable[[list[str]], np.ndarray]

_trava = threading.Lock()
_modelos: dict[str, object] = {}


def criar_embutidor(nome_modelo: str) -> Embutidor:
    def embutir(textos: list[str]) -> np.ndarray:
        with _trava:
            if nome_modelo not in _modelos:
                from fastembed import TextEmbedding

                _modelos[nome_modelo] = TextEmbedding(nome_modelo)
            modelo = _modelos[nome_modelo]
            vetores = np.array(list(modelo.embed(textos, batch_size=16)), dtype=np.float32)
        normas = np.linalg.norm(vetores, axis=1, keepdims=True)
        return vetores / np.clip(normas, 1e-9, None)

    return embutir

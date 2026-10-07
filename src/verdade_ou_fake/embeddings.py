"""Embeddings multilíngues rodando em CPU via ONNX (fastembed).

O modelo é multilíngue de propósito: a notícia chega em português e a
literatura está em inglês. Com o mesmo espaço vetorial para os dois idiomas,
a pergunta em PT encontra o resumo em EN sem etapa de tradução.

ONNX em vez de PyTorch: a imagem de produção fica ~1,5 GB menor e o modelo
carrega em cerca de um segundo.
"""

import threading
from collections.abc import Callable

import numpy as np

Embutidor = Callable[[list[str]], np.ndarray]

_trava = threading.Lock()
_modelos: dict[str, object] = {}


def criar_embutidor(nome_modelo: str) -> Embutidor:
    """Devolve uma função texto[] → matriz float32 com linhas de norma 1."""

    def embutir(textos: list[str]) -> np.ndarray:
        with _trava:
            if nome_modelo not in _modelos:
                from fastembed import TextEmbedding  # import tardio: é pesado

                _modelos[nome_modelo] = TextEmbedding(nome_modelo)
            modelo = _modelos[nome_modelo]
            vetores = np.array(list(modelo.embed(textos, batch_size=16)), dtype=np.float32)
        normas = np.linalg.norm(vetores, axis=1, keepdims=True)
        return vetores / np.clip(normas, 1e-9, None)

    return embutir

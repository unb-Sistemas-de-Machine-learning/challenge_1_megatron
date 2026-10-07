"""Recuperação híbrida: busca vetorial + busca lexical, fundidas por RRF.

As duas buscas erram em lugares diferentes. A vetorial entende paráfrase e
cruza idiomas, mas confunde fármacos de nome parecido; a lexical (BM25) acerta
o nome exato do medicamento, mas não sabe que "pressão alta" é "hypertension".
A fusão por Reciprocal Rank Fusion combina as duas ordenações sem precisar
calibrar escalas de score diferentes.
"""

import re
import threading
from dataclasses import dataclass

import numpy as np

from verdade_ou_fake.banco import Banco, Documento
from verdade_ou_fake.embeddings import Embutidor

K_RRF = 60
CANDIDATOS_POR_BUSCA = 30
# Hierarquia de evidência: revisão sistemática vale mais que estudo isolado.
BONUS_POR_TIPO = {
    "Systematic Review": 1.20,
    "Meta-Analysis": 1.20,
    "Randomized Controlled Trial": 1.08,
}
PALAVRAS_VAZIAS = {
    "a", "o", "e", "de", "da", "do", "das", "dos", "em", "para", "por", "com", "que", "um",
    "uma", "os", "as", "no", "na", "nos", "nas", "ao", "se", "mais", "como", "ou", "ser",
    "the", "of", "and", "in", "to", "for", "is", "are", "on", "with", "by", "an", "be", "or",
    "as", "at", "that", "this", "it", "from", "does", "do", "can", "not", "trata", "cura",
    "treat", "treats", "cure", "cures", "effective", "efficacy",
}  # fmt: skip


@dataclass
class Trecho:
    documento: Documento
    similaridade: float  # cosseno com a consulta; 0 se veio só da busca lexical
    pontuacao: float


def montar_expressao_fts(texto: str, maximo_termos: int = 12) -> str:
    """Transforma texto livre numa expressão FTS5 segura (termos unidos por OR)."""
    termos: list[str] = []
    for palavra in re.findall(r"[\w-]+", texto.lower()):
        palavra = palavra.strip("-_")
        if len(palavra) < 3 or palavra in PALAVRAS_VAZIAS or palavra in termos:
            continue
        termos.append(palavra)
    return " OR ".join(f'"{termo}"' for termo in termos[:maximo_termos])


class Recuperador:
    def __init__(self, banco: Banco, embutir: Embutidor):
        self._banco = banco
        self._embutir = embutir
        self._trava = threading.Lock()
        self._ids = np.zeros(0, dtype=np.int64)
        self._matriz = np.zeros((0, 0), dtype=np.float32)
        self._total_carregado = -1

    def _garantir_matriz(self) -> None:
        """Recarrega os vetores se a base cresceu (ingestão ou busca ao vivo)."""
        total = self._banco.total_documentos()
        with self._trava:
            if total != self._total_carregado:
                self._ids, self._matriz = self._banco.carregar_embeddings()
                self._total_carregado = total

    def buscar(self, consulta: str, termos_lexicais: str = "", k: int = 5) -> list[Trecho]:
        self._garantir_matriz()
        if self._matriz.shape[0] == 0:
            return []

        vetor = self._embutir([consulta])[0]
        similaridades = self._matriz @ vetor
        ordem = np.argsort(-similaridades)[:CANDIDATOS_POR_BUSCA]
        ids_vetorial = [int(self._ids[i]) for i in ordem]
        similaridade_por_id = {int(self._ids[i]): float(similaridades[i]) for i in ordem}

        ids_lexical = self._banco.buscar_texto(
            montar_expressao_fts(termos_lexicais or consulta), CANDIDATOS_POR_BUSCA
        )

        pontos: dict[int, float] = {}
        for lista in (ids_vetorial, ids_lexical):
            for posicao, doc_id in enumerate(lista):
                pontos[doc_id] = pontos.get(doc_id, 0.0) + 1.0 / (K_RRF + posicao + 1)

        documentos = {d.id: d for d in self._banco.obter_documentos(list(pontos))}
        trechos = []
        for doc_id, pontuacao in pontos.items():
            documento = documentos.get(doc_id)
            if documento is None:
                continue
            bonus = max((BONUS_POR_TIPO.get(t, 1.0) for t in documento.tipos), default=1.0)
            if doc_id not in similaridade_por_id:
                # Veio só da busca lexical: calcula o cosseno para a checagem de cobertura.
                indice = int(np.searchsorted(self._ids, doc_id))
                similaridade_por_id[doc_id] = float(similaridades[indice])
            trechos.append(
                Trecho(documento, similaridade_por_id[doc_id], pontuacao * bonus)
            )

        trechos.sort(key=lambda t: -t.pontuacao)
        return trechos[:k]

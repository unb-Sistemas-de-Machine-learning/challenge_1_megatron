"""Persistência em SQLite: base de conhecimento, cache e registro de uso.

Um único arquivo guarda três coisas:

- `documentos` (+ índice FTS5 `documentos_fts`): os resumos científicos e seus
  embeddings. É a base de conhecimento do RAG.
- `consultas`: cada análise feita — veredito, fontes citadas, latência, modelo
  e o feedback do usuário. É a matéria-prima do monitoramento (P8) e do ciclo
  de feedback (P9) de Kreuzberger et al.
- `paginas`: cache do texto extraído de cada link, para não baixar duas vezes.

Por que SQLite e não um banco vetorial dedicado: a base tem alguns milhares de
documentos, e nessa escala a busca vetorial exata com numpy leva milissegundos.
Um servidor de banco só acrescentaria um ponto de falha (ver ADR 0002).
"""

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ESQUEMA = """
CREATE TABLE IF NOT EXISTS documentos (
    id INTEGER PRIMARY KEY,
    fonte TEXT NOT NULL,
    id_externo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    texto TEXT NOT NULL,
    url TEXT NOT NULL,
    ano INTEGER,
    tipos TEXT NOT NULL DEFAULT '[]',
    origem TEXT NOT NULL DEFAULT 'lote',
    embedding BLOB NOT NULL,
    criado_em REAL NOT NULL,
    UNIQUE (fonte, id_externo)
);
CREATE VIRTUAL TABLE IF NOT EXISTS documentos_fts USING fts5(
    titulo, texto, tokenize = "unicode61 remove_diacritics 2"
);
CREATE TABLE IF NOT EXISTS consultas (
    id INTEGER PRIMARY KEY,
    criado_em REAL NOT NULL,
    chave TEXT NOT NULL,
    tipo_entrada TEXT NOT NULL,
    alegacao TEXT,
    veredito TEXT,
    confianca TEXT,
    fontes TEXT NOT NULL DEFAULT '[]',
    citacoes_validas INTEGER,
    busca_ao_vivo INTEGER NOT NULL DEFAULT 0,
    do_cache INTEGER NOT NULL DEFAULT 0,
    modelo TEXT,
    latencia_ms INTEGER,
    eventos TEXT,
    feedback INTEGER
);
CREATE INDEX IF NOT EXISTS consultas_chave ON consultas (chave, criado_em);
CREATE TABLE IF NOT EXISTS paginas (
    url TEXT PRIMARY KEY,
    titulo TEXT NOT NULL,
    texto TEXT NOT NULL,
    criado_em REAL NOT NULL
);
"""


@dataclass
class Documento:
    id: int
    fonte: str
    id_externo: str
    titulo: str
    texto: str
    url: str
    ano: int | None
    tipos: list[str]


class Banco:
    """Conexão única protegida por trava: o serviço é um processo só."""

    def __init__(self, caminho: Path | str):
        if str(caminho) != ":memory:":
            Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(caminho), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._trava = threading.RLock()
        with self._trava:
            self._con.execute("PRAGMA journal_mode = WAL")
            self._con.executescript(ESQUEMA)
            self._con.commit()

    # ------------------------------------------------------------ documentos

    def inserir_documentos(
        self, documentos: list[dict], embeddings: np.ndarray, origem: str = "lote"
    ) -> int:
        """Insere documentos novos; os já existentes (fonte, id_externo) são ignorados."""
        inseridos = 0
        with self._trava:
            for doc, vetor in zip(documentos, embeddings, strict=True):
                cursor = self._con.execute(
                    "INSERT OR IGNORE INTO documentos "
                    "(fonte, id_externo, titulo, texto, url, ano, tipos, origem, embedding, criado_em) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        doc["fonte"],
                        doc["id_externo"],
                        doc["titulo"],
                        doc["texto"],
                        doc["url"],
                        doc.get("ano"),
                        json.dumps(doc.get("tipos", []), ensure_ascii=False),
                        origem,
                        np.asarray(vetor, dtype=np.float32).tobytes(),
                        time.time(),
                    ),
                )
                if cursor.rowcount:
                    self._con.execute(
                        "INSERT INTO documentos_fts (rowid, titulo, texto) VALUES (?, ?, ?)",
                        (cursor.lastrowid, doc["titulo"], doc["texto"]),
                    )
                    inseridos += 1
            self._con.commit()
        return inseridos

    def ids_existentes(self, fonte: str) -> set[str]:
        with self._trava:
            linhas = self._con.execute(
                "SELECT id_externo FROM documentos WHERE fonte = ?", (fonte,)
            ).fetchall()
        return {linha[0] for linha in linhas}

    def total_documentos(self) -> int:
        with self._trava:
            return self._con.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]

    def carregar_embeddings(self) -> tuple[np.ndarray, np.ndarray]:
        """Devolve (ids, matriz) com todos os vetores, para a busca em memória."""
        with self._trava:
            linhas = self._con.execute("SELECT id, embedding FROM documentos ORDER BY id").fetchall()
        if not linhas:
            return np.zeros(0, dtype=np.int64), np.zeros((0, 0), dtype=np.float32)
        ids = np.array([linha[0] for linha in linhas], dtype=np.int64)
        matriz = np.vstack([np.frombuffer(linha[1], dtype=np.float32) for linha in linhas])
        return ids, matriz

    def buscar_texto(self, expressao_fts: str, limite: int) -> list[int]:
        """Busca lexical (BM25). Devolve ids em ordem de relevância."""
        if not expressao_fts:
            return []
        with self._trava:
            try:
                linhas = self._con.execute(
                    "SELECT rowid FROM documentos_fts WHERE documentos_fts MATCH ? "
                    "ORDER BY bm25(documentos_fts, 3.0, 1.0) LIMIT ?",
                    (expressao_fts, limite),
                ).fetchall()
            except sqlite3.OperationalError:
                return []
        return [linha[0] for linha in linhas]

    def obter_documentos(self, ids: list[int]) -> list[Documento]:
        if not ids:
            return []
        marcas = ",".join("?" * len(ids))
        with self._trava:
            linhas = self._con.execute(
                f"SELECT * FROM documentos WHERE id IN ({marcas})", list(ids)
            ).fetchall()
        por_id = {
            linha["id"]: Documento(
                id=linha["id"],
                fonte=linha["fonte"],
                id_externo=linha["id_externo"],
                titulo=linha["titulo"],
                texto=linha["texto"],
                url=linha["url"],
                ano=linha["ano"],
                tipos=json.loads(linha["tipos"]),
            )
            for linha in linhas
        }
        return [por_id[i] for i in ids if i in por_id]

    # -------------------------------------------------------------- consultas

    def registrar_consulta(self, **campos) -> int:
        campos.setdefault("criado_em", time.time())
        for chave in ("fontes", "eventos"):
            if chave in campos and not isinstance(campos[chave], str):
                campos[chave] = json.dumps(campos[chave], ensure_ascii=False)
        colunas = ", ".join(campos)
        marcas = ", ".join("?" * len(campos))
        with self._trava:
            cursor = self._con.execute(
                f"INSERT INTO consultas ({colunas}) VALUES ({marcas})", list(campos.values())
            )
            self._con.commit()
            return cursor.lastrowid

    def buscar_cache(self, chave: str, validade_segundos: float) -> list[dict] | None:
        """Eventos da última resposta gerada (não replay) para a mesma entrada."""
        with self._trava:
            linha = self._con.execute(
                "SELECT eventos FROM consultas WHERE chave = ? AND do_cache = 0 "
                "AND eventos IS NOT NULL AND criado_em > ? ORDER BY criado_em DESC LIMIT 1",
                (chave, time.time() - validade_segundos),
            ).fetchone()
        return json.loads(linha[0]) if linha else None

    def registrar_feedback(self, consulta_id: int, valor: int) -> bool:
        with self._trava:
            cursor = self._con.execute(
                "UPDATE consultas SET feedback = ? WHERE id = ?", (valor, consulta_id)
            )
            self._con.commit()
            return cursor.rowcount > 0

    def metricas(self) -> dict:
        """Indicadores de operação para o painel /api/metricas."""
        with self._trava:
            geral = self._con.execute(
                "SELECT COUNT(*) AS total, SUM(do_cache) AS do_cache, "
                "SUM(busca_ao_vivo) AS ao_vivo, "
                "SUM(feedback = 1) AS positivos, SUM(feedback = -1) AS negativos, "
                "AVG(CASE WHEN do_cache = 0 THEN citacoes_validas END) AS citacoes_medias "
                "FROM consultas"
            ).fetchone()
            vereditos = self._con.execute(
                "SELECT veredito, COUNT(*) FROM consultas GROUP BY veredito"
            ).fetchall()
            latencias = [
                linha[0]
                for linha in self._con.execute(
                    "SELECT latencia_ms FROM consultas WHERE do_cache = 0 "
                    "AND latencia_ms IS NOT NULL ORDER BY latencia_ms"
                )
            ]
            documentos = self._con.execute(
                "SELECT origem, COUNT(*) FROM documentos GROUP BY origem"
            ).fetchall()

        def percentil(p: float) -> int | None:
            if not latencias:
                return None
            return latencias[min(len(latencias) - 1, int(p * len(latencias)))]

        return {
            "consultas": geral["total"] or 0,
            "respondidas_do_cache": geral["do_cache"] or 0,
            "com_busca_ao_vivo": geral["ao_vivo"] or 0,
            "feedback_positivo": geral["positivos"] or 0,
            "feedback_negativo": geral["negativos"] or 0,
            "citacoes_validas_media": round(geral["citacoes_medias"], 2)
            if geral["citacoes_medias"] is not None
            else None,
            "latencia_ms_p50": percentil(0.50),
            "latencia_ms_p95": percentil(0.95),
            "vereditos": {linha[0] or "sem_veredito": linha[1] for linha in vereditos},
            "documentos_por_origem": {linha[0]: linha[1] for linha in documentos},
        }

    # ---------------------------------------------------------------- páginas

    def obter_pagina(self, url: str) -> tuple[str, str] | None:
        with self._trava:
            linha = self._con.execute(
                "SELECT titulo, texto FROM paginas WHERE url = ?", (url,)
            ).fetchone()
        return (linha[0], linha[1]) if linha else None

    def guardar_pagina(self, url: str, titulo: str, texto: str) -> None:
        with self._trava:
            self._con.execute(
                "INSERT OR REPLACE INTO paginas (url, titulo, texto, criado_em) VALUES (?, ?, ?, ?)",
                (url, titulo, texto, time.time()),
            )
            self._con.commit()

    def fechar(self) -> None:
        with self._trava:
            self._con.close()

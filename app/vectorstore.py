"""
VectorStore en NumPy.

Para un corpus universitario (reglamentos, mallas, guías: del orden de
miles de fragmentos, no millones) una multiplicación matriz-vector es
instantánea y evita dependencias nativas como FAISS, lo que importa al
desplegar en una VM pequeña de capa gratuita.

El índice se guarda como JSON (metadatos + texto) y un .npy (vectores),
para poder inspeccionarlo con un editor de texto normal si hace falta.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .chunking import Chunk


class VectorStore:
    def __init__(self):
        self.vectors: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        self.chunks: list[Chunk] = []

    def build(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        self.chunks = chunks
        # Normaliza para que el producto punto sea similitud coseno.
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.vectors = vectors / norms

    def search(self, query_vector: np.ndarray, top_k: int) -> list[tuple[Chunk, float]]:
        if len(self.chunks) == 0:
            return []
        q = query_vector / (np.linalg.norm(query_vector) or 1.0)
        scores = self.vectors @ q
        top_k = min(top_k, len(scores))
        top_idx = np.argpartition(-scores, top_k - 1)[:top_k]
        top_idx = top_idx[np.argsort(-scores[top_idx])]
        return [(self.chunks[i], float(scores[i])) for i in top_idx]

    def save(self, index_path: Path) -> None:
        """Guarda todo (metadatos + vectores) en un único JSON.

        Se eligió JSON puro (en vez de un .npy binario aparte) a propósito:
        este mismo archivo lo tiene que poder leer tanto este backend en
        Python como la función serverless de Netlify (Node.js) cuando se
        despliega ahí — un formato portable evita mantener dos formatos
        de índice sincronizados.
        """
        index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "chunks": [asdict(c) for c in self.chunks],
            "vectors": self.vectors.tolist(),
        }
        index_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def load(self, index_path: Path) -> None:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        self.chunks = [Chunk(**m) for m in payload["chunks"]]
        vectors = payload["vectors"]
        self.vectors = (
            np.array(vectors, dtype=np.float32) if vectors
            else np.zeros((0, 0), dtype=np.float32)
        )

    def is_empty(self) -> bool:
        return len(self.chunks) == 0

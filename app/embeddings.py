"""
Embedder: convierte texto en vectores.

Detrás de una sola interfaz (`embed_texts`) hay dos implementaciones:
- gemini: llama a la API de embeddings de Google (gratis, recomendado).
- hash:   proyección determinista sin red ni modelo, solo para probar
          que el pipeline de ingesta/recuperación funciona sin gastar
          cuota ni necesitar API key.

Cambiar de proveedor es cambiar la variable EMBEDDER en .env; ningún
módulo por encima de este (vectorstore, agent) sabe cuál está activo.
"""
from __future__ import annotations

import hashlib
import time

import numpy as np
import requests

from . import config

HASH_DIM = 256


def _embed_hash(texts: list[str]) -> np.ndarray:
    """Proyección determinista sin red ni modelo, solo para pruebas locales."""
    vectors = []
    for text in texts:
        vec = np.zeros(HASH_DIM, dtype=np.float32)
        # Se combinan varios hashes (uno por bloque de 32 bytes) en vez de
        # reinterpretar bytes crudos como floats IEEE-754, lo que podría
        # producir NaN/Inf según el patrón de bits.
        for offset in range(0, HASH_DIM, 32):
            block = hashlib.sha256(f"{text}|{offset}".encode("utf-8")).digest()
            values = np.frombuffer(block, dtype=np.uint8).astype(np.float32)
            take = min(32, HASH_DIM - offset)
            vec[offset:offset + take] = (values[:take] - 127.5) / 127.5
        norm = np.linalg.norm(vec) or 1.0
        vectors.append(vec / norm)
    return np.vstack(vectors)


def _embed_gemini(texts: list[str]) -> np.ndarray:
    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY no está configurada. Define EMBEDDER=hash "
            "para probar sin API key, o agrega la key en .env."
        )
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_EMBED_MODEL}:batchEmbedContents"
    )
    requests_body = {
        "requests": [
            {
                "model": f"models/{config.GEMINI_EMBED_MODEL}",
                "content": {"parts": [{"text": text}]},
            }
            for text in texts
        ]
    }

    # La capa gratuita de gemini-embedding-001 tiene una cuota de
    # solicitudes-por-minuto bastante baja. Como la ingesta corre una
    # sola vez y nadie la está esperando en vivo, ante un 429 simplemente
    # esperamos y reintentamos en vez de fallar.
    max_retries = 6
    wait_s = 20
    for attempt in range(1, max_retries + 1):
        resp = requests.post(
            url,
            params={"key": config.GEMINI_API_KEY},
            json=requests_body,
            timeout=60,
        )
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            sleep_s = int(retry_after) if retry_after else wait_s
            print(f"  cuota alcanzada (429), esperando {sleep_s}s "
                  f"y reintentando ({attempt}/{max_retries})...")
            time.sleep(sleep_s)
            wait_s = min(wait_s * 2, 120)
            continue

        resp.raise_for_status()
        data = resp.json()
        vectors = [e["values"] for e in data["embeddings"]]
        return np.array(vectors, dtype=np.float32)

    raise RuntimeError(
        "Se agotaron los reintentos por límite de cuota (429) de Gemini. "
        "Espera unos minutos y vuelve a correr `python -m app.ingest`."
    )


_BACKENDS = {
    "gemini": _embed_gemini,
    "hash": _embed_hash,
}


def embed_texts(texts: list[str], backend: str | None = None) -> np.ndarray:
    if not texts:
        return np.zeros((0, HASH_DIM), dtype=np.float32)
    backend = backend or config.EMBEDDER
    fn = _BACKENDS.get(backend)
    if fn is None:
        raise ValueError(f"Backend de embeddings desconocido: {backend}")
    # La API de embeddings de Gemini acepta lotes; se manda en tandas para
    # no exceder límites de tamaño de request.
    batch_size = 100
    chunks = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
    results = [fn(chunk) for chunk in chunks]
    return np.vstack(results)

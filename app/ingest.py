"""
Construye el índice vectorial a partir de los documentos en `data/`.

Uso:
    python -m app.ingest

Se ejecuta una sola vez después de agregar o cambiar documentos (no en
cada pregunta), así que el costo de red de generar embeddings no le pega
a la latencia de las consultas de quien usa el agente.
"""
from __future__ import annotations

import sys
import time

from . import config, embeddings
from .chunking import chunk_all
from .loaders import load_all
from .vectorstore import VectorStore


def main() -> None:
    start = time.time()
    print(f"Leyendo documentos de {config.DATA_DIR} ...")
    passages = load_all(config.DATA_DIR)
    if not passages:
        print(
            f"No se encontraron documentos soportados en {config.DATA_DIR} "
            f"(formatos: pdf, txt, md, csv). Agrega archivos y vuelve a correr."
        )
        sys.exit(1)

    ocr_count = sum(1 for p in passages if p.via_ocr)
    print(f"{len(passages)} fragmentos de página/fila leídos "
          f"({ocr_count} vía OCR).")

    chunks = chunk_all(passages)
    print(f"{len(chunks)} chunks generados (tamaño~{config.CHUNK_SIZE}, "
          f"solape~{config.CHUNK_OVERLAP}).")

    print(f"Generando embeddings con backend '{config.EMBEDDER}' ...")
    vectors = embeddings.embed_texts([c.text for c in chunks])

    store = VectorStore()
    store.build(chunks, vectors)
    store.save(config.INDEX_PATH)

    elapsed = time.time() - start
    print(f"Índice guardado en {config.INDEX_PATH} ({elapsed:.1f}s).")


if __name__ == "__main__":
    main()

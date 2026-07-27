"""
Prueba de humo end-to-end: ingesta + recuperación + respuesta, usando los
documentos de ejemplo y los backends sin red (EMBEDDER=hash, LLM=echo)
para que corra en CI sin necesitar ninguna API key.
"""
import os
import shutil
from pathlib import Path

os.environ.setdefault("EMBEDDER", "hash")
os.environ.setdefault("LLM", "echo")

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    d.mkdir()
    for f in (ROOT / "data" / "ejemplo").iterdir():
        if f.is_file():
            shutil.copy(f, d / f.name)

    index_path = tmp_path / "index" / "index.json"
    monkeypatch.setenv("DATA_DIR", str(d))
    monkeypatch.setenv("INDEX_PATH", str(index_path))

    # Los módulos leen config al importarse, así que se recargan después
    # de fijar las variables de entorno para esta prueba.
    import importlib
    from app import config
    importlib.reload(config)
    return d, index_path


def test_loaders_extract_text_and_ocr(data_dir):
    from app.loaders import load_all
    from app import config

    passages = load_all(config.DATA_DIR)
    assert len(passages) >= 3

    ocr_passages = [p for p in passages if p.via_ocr]
    assert ocr_passages, "el PDF de ejemplo tipo escaneo debería pasar por OCR"
    assert "beca" in ocr_passages[0].text.lower()


def test_ingest_and_answer(data_dir):
    from app import config
    from app.chunking import chunk_all
    from app.loaders import load_all
    from app.vectorstore import VectorStore
    from app import embeddings, agent

    passages = load_all(config.DATA_DIR)
    chunks = chunk_all(passages)
    assert len(chunks) > 0

    vectors = embeddings.embed_texts([c.text for c in chunks])
    assert vectors.shape[0] == len(chunks)

    store = VectorStore()
    store.build(chunks, vectors)

    result = agent.answer_question("¿cuál es el promedio mínimo para aprobar?", store)
    assert result.sources, "la respuesta debería traer al menos una fuente citada"
    assert result.provider == "echo"


def test_agent_without_index_gives_friendly_message():
    from app.agent import answer_question
    from app.vectorstore import VectorStore

    empty_store = VectorStore()
    result = answer_question("¿hay algo indexado?", empty_store)
    assert "no hay documentos indexados" in result.answer.lower()
    assert result.sources == []

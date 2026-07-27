"""
Troceado de Passages en Chunks del tamaño adecuado para embeddings.

Se corta por oración (no a la mitad de una palabra ni de una idea) y se
deja un solapamiento entre trozos consecutivos para no perder contexto
que quede justo en el borde de un corte.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import config
from .loaders import Passage

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?¿¡])\s+")


@dataclass
class Chunk:
    text: str
    source: str
    locator: str
    chunk_id: int
    via_ocr: bool = False


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    return _SENTENCE_SPLIT.split(text)


def chunk_passage(passage: Passage, chunk_id_start: int) -> list[Chunk]:
    sentences = _split_sentences(passage.text)
    chunks: list[Chunk] = []
    current: list[str] = []
    current_len = 0
    chunk_id = chunk_id_start

    def flush():
        nonlocal current, current_len, chunk_id
        if current:
            chunks.append(Chunk(
                text=" ".join(current),
                source=passage.source,
                locator=passage.locator,
                chunk_id=chunk_id,
                via_ocr=passage.via_ocr,
            ))
            chunk_id += 1

    for sentence in sentences:
        if current_len + len(sentence) > config.CHUNK_SIZE and current:
            flush()
            # Solapamiento: se conservan las últimas oraciones del trozo
            # anterior para no perder contexto en el borde del corte.
            overlap_sentences = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) > config.CHUNK_OVERLAP:
                    break
                overlap_sentences.insert(0, s)
                overlap_len += len(s)
            current = overlap_sentences
            current_len = overlap_len

        current.append(sentence)
        current_len += len(sentence)

    flush()
    return chunks


def chunk_all(passages: list[Passage]) -> list[Chunk]:
    chunks: list[Chunk] = []
    next_id = 0
    for passage in passages:
        new_chunks = chunk_passage(passage, next_id)
        chunks.extend(new_chunks)
        next_id += len(new_chunks)
    return chunks

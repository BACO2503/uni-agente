"""
Agent: une recuperación (vectorstore) + generación (llm) en una respuesta
con citas verificables.

El prompt instruye al modelo explícitamente a:
1) contestar solo con lo que está en los fragmentos recuperados,
2) marcar cada afirmación con [n] apuntando al fragmento de donde salió,
3) decir con claridad cuando la respuesta no está en los documentos,
   en vez de inventar algo plausible.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config, embeddings, llm
from .chunking import Chunk
from .vectorstore import VectorStore

SYSTEM_PROMPT = """Eres {agent_name}, un asistente que responde preguntas de \
estudiantes y colaboradores basándose ÚNICAMENTE en los fragmentos de \
documentos que se te entregan a continuación. Reglas estrictas:

1. No inventes ni completes con conocimiento externo. Si la respuesta no \
está en los fragmentos, dilo explícitamente ("No encontré esa información \
en los documentos disponibles.").
2. Cada afirmación debe llevar una cita entre corchetes, ej. [1], [2], que \
apunte al número de fragmento de donde salió.
3. Responde en español, de forma clara y directa, como lo haría un asesor \
o consultor universitario.

Fragmentos disponibles:
{context}

Pregunta: {question}

Respuesta (con citas [n]):"""


@dataclass
class Source:
    n: int
    source: str
    locator: str
    text: str
    via_ocr: bool = False


@dataclass
class AnswerResult:
    answer: str
    sources: list[Source]
    provider: str


def _format_context(retrieved: list[tuple[Chunk, float]]) -> tuple[str, list[Source]]:
    lines = []
    sources = []
    for i, (chunk, score) in enumerate(retrieved, start=1):
        lines.append(f"[{i}] (fuente: {chunk.source}, {chunk.locator})\n{chunk.text}")
        sources.append(Source(
            n=i, source=chunk.source, locator=chunk.locator,
            text=chunk.text, via_ocr=chunk.via_ocr,
        ))
    return "\n\n".join(lines), sources


def answer_question(question: str, store: VectorStore, top_k: int | None = None) -> AnswerResult:
    if store.is_empty():
        return AnswerResult(
            answer=(
                "Todavía no hay documentos indexados. Ejecuta la ingesta "
                "(`python -m app.ingest`) después de colocar archivos en `data/`."
            ),
            sources=[],
            provider="none",
        )

    top_k = top_k or config.TOP_K
    query_vector = embeddings.embed_texts([question])[0]
    retrieved = store.search(query_vector, top_k)
    context, sources = _format_context(retrieved)

    prompt = SYSTEM_PROMPT.format(
        agent_name=config.AGENT_NAME,
        context=context,
        question=question,
    )

    text, provider = llm.generate(prompt)
    return AnswerResult(answer=text.strip(), sources=sources, provider=provider)

"""
API FastAPI del agente.

Endpoints:
  GET  /api/health       -> estado simple, para monitoreo
  GET  /api/diagnostico  -> qué proveedores de IA están configurados
  POST /api/ask          -> {"question": "..."} -> respuesta + citas
  GET  /                 -> frontend estático (web/index.html)

El índice se carga una sola vez al arrancar el servidor (lifespan), no en
cada petición: recargarlo por request sería lento y tumbaría una VM
pequeña con el primer usuario concurrente.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent, config, llm
from .vectorstore import VectorStore

store = VectorStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    index_file = config.INDEX_PATH
    if index_file.exists():
        store.load(index_file)
        print(f"Índice cargado: {len(store.chunks)} chunks.")
    else:
        print(
            "Aviso: no hay índice construido todavía. "
            "Corre `python -m app.ingest` y reinicia el servidor."
        )
    yield


app = FastAPI(title=config.AGENT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


class SourceOut(BaseModel):
    n: int
    source: str
    locator: str
    text: str
    via_ocr: bool = False


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    provider: str


@app.get("/api/health")
def health():
    return {"status": "ok", "chunks_indexados": len(store.chunks)}


@app.get("/api/diagnostico")
def diagnostico():
    return {
        "modo_llm": config.LLM,
        "orden_fallback": config.LLM_FALLBACK_ORDER,
        "proveedores": llm.diagnostico(),
        "embedder": config.EMBEDDER,
        "chunks_indexados": len(store.chunks),
    }


@app.post("/api/ask", response_model=AskResponse)
def ask(payload: AskRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")

    try:
        result = agent.answer_question(question, store)
    except llm.QuotaExhaustedError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return AskResponse(
        answer=result.answer,
        sources=[SourceOut(**s.__dict__) for s in result.sources],
        provider=result.provider,
    )


# Frontend estático servido desde el mismo proceso: un solo deploy, una
# sola URL, sin problemas de CORS entre frontend y backend. La misma
# estructura (web/assets/) es la que usa el publish directory de Netlify
# en el deploy en la nube, así que /assets/style.css y /assets/script.js
# resuelven igual en ambos entornos.
app.mount("/assets", StaticFiles(directory=config.BASE_DIR / "web" / "assets"), name="assets")


@app.get("/")
def index():
    return FileResponse(config.BASE_DIR / "web" / "index.html")

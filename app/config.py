"""
Configuración de la aplicación.

Todo se controla por variables de entorno (ver .env.example) para poder
cambiar de proveedor de IA, de modelo de embeddings o de puerto sin tocar
código. Ningún módulo por encima de este debería leer os.environ
directamente: todo pasa por aquí.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
INDEX_PATH = Path(os.getenv("INDEX_PATH", BASE_DIR / "index" / "index.json"))

# --- Proveedor de generación (LLM) ---
# fallback  -> intenta gemini, luego groq, luego cerebras
# gemini / groq / cerebras -> fuerza un solo proveedor
# echo      -> no llama a ninguna API, devuelve el contexto recuperado
#              (sirve para probar el pipeline de RAG sin gastar cuota)
LLM = os.getenv("LLM", "fallback")
LLM_FALLBACK_ORDER = [p.strip() for p in os.getenv(
    "LLM_FALLBACK_ORDER", "gemini,groq,cerebras"
).split(",") if p.strip()]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")

# --- Embeddings ---
# gemini -> usa la API de embeddings de Google (gratis, recomendado)
# hash   -> proyección determinista sin red ni modelo (solo para pruebas)
EMBEDDER = os.getenv("EMBEDDER", "gemini")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")

# --- Recuperación / troceado ---
TOP_K = int(os.getenv("TOP_K", "5"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

# --- OCR ---
# Cuando una página de PDF no tiene capa de texto (es un escaneo/foto),
# se renderiza como imagen y se le aplica OCR con Tesseract.
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"
OCR_LANG = os.getenv("OCR_LANG", "spa+eng")
OCR_MIN_CHARS_PER_PAGE = int(os.getenv("OCR_MIN_CHARS_PER_PAGE", "25"))

# --- Servidor ---
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]

AGENT_NAME = os.getenv("AGENT_NAME", "Asesor UNI")

"""
Carga de documentos → lista de Passage.

Un Passage es un fragmento de texto con su procedencia (archivo + página o
fila) para poder citar exactamente de dónde salió cada dato.

Formatos soportados: .pdf (con detección automática de páginas escaneadas
y OCR), .txt, .md, .csv. La lista es corta a propósito: son los formatos
reales de la documentación universitaria de este proyecto. Añadir un
formato nuevo (.docx, .xlsx, .pptx...) significa agregar una función
`_load_xxx` y una línea en `EXTENSION_HANDLERS`; el resto del pipeline
(chunking, embeddings, index) no cambia.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

from . import config

try:
    import pytesseract
except ImportError:  # pragma: no cover - OCR es opcional en tiempo de import
    pytesseract = None


@dataclass
class Passage:
    text: str
    source: str      # nombre del archivo, ej. "reglamento_estudiantil.pdf"
    locator: str      # ej. "página 4" o "fila 12"
    via_ocr: bool = False


def _load_pdf(path: Path) -> list[Passage]:
    passages: list[Passage] = []
    doc = fitz.open(path)
    for page_index in range(len(doc)):
        page = doc[page_index]
        text = page.get_text("text").strip()

        used_ocr = False
        if config.OCR_ENABLED and len(text) < config.OCR_MIN_CHARS_PER_PAGE:
            ocr_text = _ocr_page(page)
            if len(ocr_text.strip()) > len(text):
                text = ocr_text.strip()
                used_ocr = True

        if text:
            passages.append(Passage(
                text=text,
                source=path.name,
                locator=f"página {page_index + 1}",
                via_ocr=used_ocr,
            ))
    doc.close()
    return passages


def _ocr_page(page: "fitz.Page", dpi: int = 300) -> str:
    """Renderiza una página como imagen y le aplica OCR con Tesseract.

    Se usa solo cuando la página casi no tiene texto extraíble (es decir,
    es un escaneo o una foto), para no pagar el costo de OCR en páginas
    normales.
    """
    if pytesseract is None:
        return ""
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix)
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    try:
        return pytesseract.image_to_string(image, lang=config.OCR_LANG)
    except pytesseract.TesseractError:
        # El idioma pedido puede no estar instalado en el sistema;
        # se reintenta solo con inglés para no perder el documento entero.
        return pytesseract.image_to_string(image, lang="eng")


def _load_text(path: Path) -> list[Passage]:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []
    return [Passage(text=text, source=path.name, locator="documento completo")]


def _load_csv(path: Path) -> list[Passage]:
    passages = []
    with path.open(encoding="utf-8", errors="ignore", newline="") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=1):
            line = "; ".join(f"{k}: {v}" for k, v in row.items() if v)
            if line:
                passages.append(Passage(text=line, source=path.name, locator=f"fila {i}"))
    return passages


EXTENSION_HANDLERS = {
    ".pdf": _load_pdf,
    ".txt": _load_text,
    ".md": _load_text,
    ".csv": _load_csv,
}

SUPPORTED_EXTENSIONS = tuple(EXTENSION_HANDLERS.keys())


def load_document(path: Path) -> list[Passage]:
    handler = EXTENSION_HANDLERS.get(path.suffix.lower())
    if handler is None:
        raise ValueError(f"Formato no soportado: {path.suffix}")
    return handler(path)


def load_all(data_dir: Path) -> list[Passage]:
    passages: list[Passage] = []
    for path in sorted(data_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in EXTENSION_HANDLERS:
            passages.extend(load_document(path))
    return passages

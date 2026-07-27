# Carpeta `data/`

Aquí van los documentos que el agente va a leer.

- **Formatos soportados:** `.pdf` (incluye PDFs escaneados/fotos, se les
  aplica OCR automáticamente), `.txt`, `.md`, `.csv`.
- **`data/ejemplo/`** contiene documentos ficticios (un reglamento
  académico, una malla curricular y un "escaneo" simulado) que se suben
  al repositorio a propósito, para que cualquiera pueda probar el agente
  sin necesitar documentos reales. **Sí forman parte del repositorio.**
- Cualquier archivo que pongas directamente en `data/` (no en
  `data/ejemplo/`) se ignora en Git (ver `.gitignore`): así puedes cargar
  tus documentos reales de la universidad —que pueden tener información
  personal o derechos de autor— sin subirlos por accidente a un
  repositorio público.

## Cómo usar tus propios documentos

1. Copia tus PDFs (reglamentos, mallas curriculares, guías, calendarios,
   escaneos de resoluciones, etc.) directamente a esta carpeta `data/`.
2. Corre la ingesta: `python -m app.ingest`
3. Levanta el servidor (`uvicorn app.api:app --reload`) y pregunta.

Si quieres probar solo con los documentos de ejemplo, copia el contenido
de `data/ejemplo/` a `data/` antes de correr la ingesta.

## Deploy en Netlify

Para el deploy en Netlify, el índice generado (`index/index.json`) se
copia a `netlify/functions/data/index.json` y **ese sí se commitea**
(ver `deploy/GUIA_NETLIFY.md`) — es lo que la función serverless lee en
producción, ya que Netlify no vuelve a correr la ingesta de Python.

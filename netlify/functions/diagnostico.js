/**
 * GET /api/diagnostico → qué proveedores tienen API key configurada.
 * Útil para confirmar que las variables de entorno quedaron bien puestas
 * en Netlify sin tener que hacer una pregunta real (que gasta cuota).
 */
const fs = require("fs");
const path = require("path");

exports.handler = async () => {
  let count = 0;
  try {
    const raw = fs.readFileSync(path.join(__dirname, "data", "index.json"), "utf-8");
    count = (JSON.parse(raw).chunks || []).length;
  } catch {
    count = 0;
  }

  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      proveedores: {
        gemini: { configurado: !!process.env.GEMINI_API_KEY },
        groq: { configurado: !!process.env.GROQ_API_KEY },
      },
      chunks_indexados: count,
    }),
  };
};

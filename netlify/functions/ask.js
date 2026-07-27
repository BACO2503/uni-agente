/**
 * POST /api/ask  →  { question: string }  →  { answer, sources, provider }
 *
 * Es el equivalente en Node de app/agent.py + app/llm.py + app/embeddings.py
 * (solo la mitad de "consulta": recuperar + generar). El OCR y la
 * generación del índice (app/ingest.py) siguen siendo responsabilidad de
 * Python y corren localmente antes de desplegar — esta función solo LEE
 * el índice ya construido (netlify/functions/data/index.json).
 *
 * Por qué está en JavaScript y no en Python: las Netlify Functions solo
 * soportan JavaScript/TypeScript y Go en tiempo de ejecución (Python solo
 * se puede usar en el paso de *build*, no como runtime de una función),
 * así que la parte que sí necesita correr en la nube se reescribió aquí.
 */
const fs = require("fs");
const path = require("path");

const AGENT_NAME = process.env.AGENT_NAME || "Asesor UNI";
const TOP_K = parseInt(process.env.TOP_K || "5", 10);

let cachedIndex = null;

function loadIndex() {
  if (cachedIndex) return cachedIndex;
  try {
    const raw = fs.readFileSync(path.join(__dirname, "data", "index.json"), "utf-8");
    cachedIndex = JSON.parse(raw);
  } catch (e) {
    // Sin índice todavía (por ejemplo, recién clonado el repo sin correr
    // la ingesta): se responde de forma amigable en vez de tronar.
    cachedIndex = { chunks: [], vectors: [] };
  }
  return cachedIndex;
}

function cosineSimilarity(a, b) {
  let dot = 0, normA = 0, normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  if (normA === 0 || normB === 0) return 0;
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

async function embedQuery(text) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error(
      "GEMINI_API_KEY no está configurada en Netlify (Site configuration → " +
      "Environment variables). Los embeddings de la pregunta dependen de Gemini."
    );
  }
  const model = process.env.GEMINI_EMBED_MODEL || "gemini-embedding-001";
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:embedContent?key=${apiKey}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: `models/${model}`,
      content: { parts: [{ text }] },
    }),
  });
  if (!res.ok) {
    throw new Error(`Gemini (embeddings) respondió ${res.status}`);
  }
  const data = await res.json();
  return data.embedding.values;
}

async function callGemini(prompt) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) throw new Error("GEMINI_API_KEY no configurada");
  const model = process.env.GEMINI_MODEL || "gemini-2.5-flash-lite";
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] }),
  });
  if (res.status === 429) throw new Error("Gemini: cuota agotada (429)");
  if (!res.ok) throw new Error(`Gemini respondió ${res.status}`);
  const data = await res.json();
  return data.candidates[0].content.parts[0].text;
}

async function callGroq(prompt) {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) throw new Error("GROQ_API_KEY no configurada");
  const model = process.env.GROQ_MODEL || "llama-3.3-70b-versatile";
  const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ model, messages: [{ role: "user", content: prompt }] }),
  });
  if (res.status === 429) throw new Error("Groq: cuota agotada (429)");
  if (!res.ok) throw new Error(`Groq respondió ${res.status}`);
  const data = await res.json();
  return data.choices[0].message.content;
}

// Cascada: intenta Gemini y, si falla o no tiene key, salta a Groq.
// Mismo comportamiento que app/llm.py del lado de Python.
async function generate(prompt) {
  const providers = [
    { name: "gemini", fn: callGemini, hasKey: !!process.env.GEMINI_API_KEY },
    { name: "groq", fn: callGroq, hasKey: !!process.env.GROQ_API_KEY },
  ];
  const errors = [];
  for (const provider of providers) {
    if (!provider.hasKey) continue;
    try {
      const text = await provider.fn(prompt);
      return { text, provider: provider.name };
    } catch (e) {
      errors.push(`${provider.name}: ${e.message}`);
    }
  }
  throw new Error(
    errors.length
      ? "Todos los proveedores configurados fallaron: " + errors.join("; ")
      : "Ningún proveedor de IA tiene API key configurada en Netlify."
  );
}

function buildPrompt(context, question) {
  return `Eres ${AGENT_NAME}, un asistente que responde preguntas de estudiantes y colaboradores basándose ÚNICAMENTE en los fragmentos de documentos que se te entregan a continuación. Reglas estrictas:

1. No inventes ni completes con conocimiento externo. Si la respuesta no está en los fragmentos, dilo explícitamente ("No encontré esa información en los documentos disponibles.").
2. Cada afirmación debe llevar una cita entre corchetes, ej. [1], [2], que apunte al número de fragmento de donde salió.
3. Responde en español, de forma clara y directa, como lo haría un asesor o consultor universitario.

Fragmentos disponibles:
${context}

Pregunta: ${question}

Respuesta (con citas [n]):`;
}

exports.handler = async (event) => {
  const headers = { "Content-Type": "application/json" };

  if (event.httpMethod !== "POST") {
    return { statusCode: 405, headers, body: JSON.stringify({ detail: "Método no permitido" }) };
  }

  let question;
  try {
    question = (JSON.parse(event.body || "{}").question || "").trim();
  } catch {
    return { statusCode: 400, headers, body: JSON.stringify({ detail: "JSON inválido" }) };
  }
  if (!question) {
    return { statusCode: 400, headers, body: JSON.stringify({ detail: "La pregunta no puede estar vacía." }) };
  }

  const index = loadIndex();
  if (!index.chunks || index.chunks.length === 0) {
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        answer:
          "Todavía no hay documentos indexados en este despliegue. Corre " +
          "`python -m app.ingest` localmente, copia el resultado a " +
          "netlify/functions/data/index.json, haz commit y vuelve a desplegar " +
          "(ver README).",
        sources: [],
        provider: "none",
      }),
    };
  }

  try {
    const queryVector = await embedQuery(question);
    const scored = index.chunks.map((chunk, i) => ({
      chunk,
      score: cosineSimilarity(queryVector, index.vectors[i]),
    }));
    scored.sort((a, b) => b.score - a.score);
    const top = scored.slice(0, TOP_K);

    const contextText = top
      .map((t, i) => `[${i + 1}] (fuente: ${t.chunk.source}, ${t.chunk.locator})\n${t.chunk.text}`)
      .join("\n\n");
    const sources = top.map((t, i) => ({
      n: i + 1,
      source: t.chunk.source,
      locator: t.chunk.locator,
      text: t.chunk.text,
      via_ocr: !!t.chunk.via_ocr,
    }));

    const { text, provider } = await generate(buildPrompt(contextText, question));

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ answer: text.trim(), sources, provider }),
    };
  } catch (e) {
    return { statusCode: 503, headers, body: JSON.stringify({ detail: e.message }) };
  }
};

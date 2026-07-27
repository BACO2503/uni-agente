/**
 * GET /api/health → { status, chunks_indexados }
 * Equivalente en Node de GET /api/health en app/api.py (Python).
 */
const fs = require("fs");
const path = require("path");

exports.handler = async () => {
  let count = 0;
  try {
    const raw = fs.readFileSync(path.join(__dirname, "data", "index.json"), "utf-8");
    const data = JSON.parse(raw);
    count = (data.chunks || []).length;
  } catch {
    count = 0;
  }
  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "ok", chunks_indexados: count }),
  };
};

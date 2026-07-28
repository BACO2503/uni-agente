# Asesor UNI

Agente de IA que responde preguntas sobre documentos internos de una
universidad (reglamentos, mallas curriculares, guías, becas...) citando
siempre el documento y la página exacta de donde salió cada dato. Es el
proyecto final del **Challenge de Alura: Agente de IA**.

**Demo en vivo:** _pendiente — se agrega el enlace de Netlify aquí después
del deploy (ver [Evidencia del deploy](#️-evidencia-del-deploy))._

---

## El problema

Un reglamento estudiantil, una malla curricular o una guía de becas
suelen ser PDFs largos (y a veces escaneados) que nadie lee completos.
La información existe, pero encontrarla a mano cuesta tiempo. Este
agente indexa esos documentos y responde en lenguaje natural, con la
cita exacta de dónde sale cada afirmación — y, si la respuesta no está
en los documentos, lo dice explícitamente en vez de inventarla.

## La solución

Un sistema RAG (*Retrieval-Augmented Generation*) clásico, con tres
particularidades pensadas para este proyecto en concreto:

- **OCR automático**: buena parte de la documentación universitaria son
  escaneos o fotos sin capa de texto. El loader detecta página por
  página si el PDF trae texto extraíble; si no, la renderiza como imagen
  y le aplica OCR con Tesseract, sin intervención manual.
- **Cascada de proveedores de IA**: el modelo de lenguaje está detrás de
  una interfaz común, y por encima corre una cascada (Gemini → Groq). Si
  el proveedor activo se queda sin cuota gratuita, el agente salta
  automáticamente al siguiente sin que quien pregunta lo note.
- **Un solo link**: frontend y backend se despliegan juntos en Netlify
  bajo el mismo dominio (el backend vive como *serverless functions* de
  Netlify), así que hay una única URL pública, sin configurar CORS ni
  mantener dos servicios por separado.

---

## Arquitectura

El proyecto tiene **dos "backends" que comparten el mismo frontend y el
mismo índice**: uno en Python (para desarrollo local y para la ingesta
de documentos) y uno en JavaScript (las funciones que corren en
Netlify). No es duplicación por gusto: Netlify Functions solo ejecuta
JavaScript/TypeScript o Go en tiempo real — Python únicamente puede
usarse en el paso de *build*, no como runtime de una función —, así que
la mitad que sí necesita vivir en la nube se reescribió en JS. La mitad
que no depende de estar "siempre corriendo" (leer los PDFs, hacer OCR,
generar el índice) se queda en Python, donde esas librerías son mucho
mejores.

```
                    ┌─────────────────────────────────────┐
                    │   SE CORRE UNA VEZ, LOCALMENTE       │
                    │   (o en CI), antes de desplegar      │
                    │                                       │
  data/*.pdf ───────►  app/loaders.py   (PDF + OCR Tesseract)│
  *.md *.csv         │  app/chunking.py (troceo por oración) │
                    │  app/embeddings.py (Gemini embeddings)│
                    │           │                           │
                    │           ▼                           │
                    │  index/index.json  (chunks + vectores)│
                    └───────────────┬───────────────────────┘
                                    │  se copia a
                                    ▼
                netlify/functions/data/index.json  (se commitea)
                                    │
      ┌─────────────────────────────┴─────────────────────────────┐
      │                    NETLIFY (producción)                    │
      │                                                             │
      │  web/ (HTML+CSS+JS) ──GET /────────► sitio estático         │
      │                                                             │
      │  web/assets/script.js ──POST /api/ask──►  netlify/functions/│
      │                                            ask.js           │
      │                                              │               │
      │                                   lee index.json, calcula    │
      │                                   similitud coseno, arma el  │
      │                                   prompt y llama a:          │
      │                                   Gemini → (fallback) Groq   │
      └─────────────────────────────────────────────────────────────┘

      ┌─────────────────────────────────────────────────────────────┐
      │              ALTERNATIVA: correr todo en local               │
      │  uvicorn app.api:app  →  FastAPI sirve /, /assets/*, /api/*  │
      │  (usa exactamente el mismo index/index.json y el mismo web/) │
      └─────────────────────────────────────────────────────────────┘
```

`web/assets/script.js` siempre llama a rutas relativas (`/api/ask`,
`/api/health`): en local esas rutas las responde FastAPI directamente;
en Netlify, `netlify.toml` las redirige a las funciones serverless. El
frontend no sabe ni le importa cuál de los dos está detrás.

### Decisiones de diseño

| Decisión | Por qué |
|---|---|
| Índice en un único JSON (no un vector store binario) | Tiene que poder leerlo tanto Python (local) como la función de Node en Netlify. JSON plano es el mínimo común denominador; para el tamaño de un corpus universitario (miles de fragmentos, no millones) el costo de no usar un formato binario es insignificante. |
| OCR solo cuando hace falta | Cada página se evalúa: si ya tiene texto extraíble, se usa tal cual; el OCR (más lento) solo corre en páginas que parecen escaneo. |
| Cascada de proveedores de IA | Gemini y Groq tienen límites de cuota gratuita distintos. Encadenarlos absorbe esos límites sin que la persona que pregunta vea un error. |
| Ingesta separada de la consulta | Construir el índice (con OCR y embeddings) es pesado y solo hace falta cuando cambian los documentos. Preguntar es liviano y frecuente. Separarlos es lo que permite que la consulta corra en una función serverless (que no puede mantener un proceso pesado corriendo) mientras la ingesta corre donde sí hay recursos completos: tu máquina. |
| Frontend sin framework | Tres archivos, sin paso de build. Netlify los sirve directo desde `web/`. |
| Modo `EMBEDDER=hash` / `LLM=echo` (solo Python) | Permite probar el pipeline de ingesta (OCR, troceo, recuperación) sin API key ni conexión a internet. |

---

## Tecnologías utilizadas

**Ingesta (local, Python 3.12):**
- FastAPI + Uvicorn — también sirve como servidor de desarrollo local
- PyMuPDF (fitz) — lectura de PDF
- Tesseract OCR (vía `pytesseract`) — texto de páginas escaneadas
- NumPy — cálculo de embeddings al construir el índice

**Consulta en producción (Netlify):**
- Netlify (Static hosting + Functions) — hosting, un solo dominio
- Node.js (JavaScript, sin dependencias externas) — lógica de recuperación y generación
- Google Gemini — embeddings y generación de texto (capa gratuita)
- Groq — generación de texto de respaldo si Gemini se queda sin cuota (capa gratuita)

**Frontend:**
- HTML + CSS + JavaScript planos (sin framework)

---

## Cómo ejecutarlo localmente

**No necesitas Windows.** El proyecto es Python + Node estándar; corre
igual en Linux (CachyOS, Ubuntu, lo que sea), macOS o Windows. En
CachyOS (basado en Arch) instala las dependencias del sistema con
`pacman` en vez de `apt`:

```bash
sudo pacman -S python python-pip tesseract tesseract-data-spa nodejs npm
```

Luego:

```bash
git clone https://github.com/<tu-usuario>/uni-agente.git
cd uni-agente
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 1. Configura tus API keys (`.env`)

```bash
cp .env.example .env
```

Abre `.env` con tu editor y pega tus keys en estas dos líneas
(instrucciones para conseguirlas más abajo, en
[¿Dónde consigo y dónde pongo las API keys?](#-dónde-consigo-y-dónde-pongo-las-api-keys)):

```dotenv
GEMINI_API_KEY=tu_key_aqui
GROQ_API_KEY=tu_key_aqui
```

### 2. Genera el índice a partir de los documentos

```bash
# para probar rápido con los documentos ficticios incluidos:
cp data/ejemplo/* data/

python -m app.ingest
```

Esto crea `index/index.json`. Cada vez que agregues o cambies
documentos en `data/`, vuelve a correr este comando.

### 3. Levanta el servidor

```bash
uvicorn app.api:app --reload
```

Abre `http://127.0.0.1:8000` — ahí está la interfaz de chat, sirviendo
del mismo proceso Python (así se ve exactamente igual a como se va a
ver en Netlify).

**¿Sin API key todavía y solo quieres ver que el pipeline funciona?**

```bash
EMBEDDER=hash LLM=echo python -m app.ingest
EMBEDDER=hash LLM=echo uvicorn app.api:app
```

`EMBEDDER=hash` genera una proyección determinista sin llamar a ningún
modelo; `LLM=echo` devuelve el contexto recuperado en vez de llamar a
una API. Sirve para confirmar que la ingesta, el OCR y la recuperación
funcionan, sin gastar cuota.

### 4. (Opcional) probar la función de Netlify en local

Si quieres probar exactamente lo mismo que va a correr en producción,
sin desplegar todavía:

```bash
npm install -g netlify-cli
cp index/index.json netlify/functions/data/index.json
netlify dev
```

`netlify dev` levanta el sitio estático y las funciones de
`netlify/functions/` en `http://localhost:8888`, con las variables de
`.env` disponibles automáticamente para las funciones.

---

## 🔑 ¿Dónde consigo y dónde pongo las API keys?

### Conseguir las keys (ambas son gratis)

| Proveedor | Dónde generarla |
|---|---|
| **Gemini** (obligatoria: se usa para embeddings y como generador principal) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → "Create API key" |
| **Groq** (opcional pero recomendada: es el respaldo si Gemini se queda sin cuota) | [console.groq.com/keys](https://console.groq.com/keys) → "Create API Key" |

### Dónde pegarlas — dos lugares distintos, uno por entorno

**1. Para correr en tu máquina (local):** van en el archivo `.env` en la
raíz del proyecto (lo creaste con `cp .env.example .env`):

```dotenv
GEMINI_API_KEY=AIzaSy...........................
GROQ_API_KEY=gsk_....................................
```

Ese archivo está en `.gitignore` — nunca se sube a GitHub.

**2. Para el deploy en Netlify:** el archivo `.env` no viaja al servidor
de Netlify, así que las keys se configuran aparte, en el panel web:

1. Entra a tu sitio en [app.netlify.com](https://app.netlify.com).
2. Ve a **Site configuration → Environment variables**.
3. Haz clic en **Add a variable → Add a single variable**.
4. Key: `GEMINI_API_KEY` — Value: tu key de Gemini. En **Scopes**, deja
   marcado al menos **Functions** (para que la función `ask.js` pueda
   leerla en tiempo de ejecución).
5. Repite el paso 3-4 para `GROQ_API_KEY`.
6. Ve a **Deploys** y dispara **Trigger deploy → Deploy site** (las
   variables nuevas no aplican hasta el siguiente deploy).

Sin esto, `ask.js` responde con un error claro indicando cuál de las dos
keys falta — no falla en silencio.

---

## ☁️ Cómo desplegar (Netlify)

Guía completa y detallada en [`deploy/GUIA_NETLIFY.md`](deploy/GUIA_NETLIFY.md).
Resumen:

1. Genera el índice localmente (`python -m app.ingest`) con tus
   documentos reales o con los de ejemplo.
2. Cópialo a la carpeta que sí se commitea:
   ```bash
   cp index/index.json netlify/functions/data/index.json
   git add netlify/functions/data/index.json
   git commit -m "data: índice para el deploy"
   git push
   ```
3. En [app.netlify.com](https://app.netlify.com): **Add new site → Import an existing project → GitHub** → elige tu repositorio. Netlify detecta `netlify.toml` automáticamente (publish = `web`, functions = `netlify/functions`); no hace falta tocar nada más ahí.
4. Agrega `GEMINI_API_KEY` y `GROQ_API_KEY` como se explicó arriba, y despliega.
5. Tu agente queda en una URL única tipo `https://tu-sitio.netlify.app`.

> `deploy/setup.sh` y `deploy/GUIA_OCI.md` también están en el repo por
> si en algún momento quieres correrlo en una VM propia (Oracle Cloud,
> u otra) en vez de Netlify — no es necesario para este proyecto, se
> dejan como alternativa.

---

## Configuración (`.env` / variables de entorno)

| Variable | Dónde se usa | Default | Qué hace |
|---|---|---|---|
| `GEMINI_API_KEY` | Python y Netlify | — | Key de Google AI Studio (embeddings + generación) |
| `GROQ_API_KEY` | Python y Netlify | — | Key de Groq (generación de respaldo) |
| `GEMINI_MODEL` | Python y Netlify | `gemini-2.5-flash-lite` | Modelo de generación de Gemini |
| `GEMINI_EMBED_MODEL` | Python y Netlify | `gemini-embedding-001` | Modelo de embeddings de Gemini ||
| `GROQ_MODEL` | Python y Netlify | `llama-3.3-70b-versatile` | Modelo de generación de Groq |
| `EMBEDDER` | Solo Python (ingesta) | `gemini` | `gemini` o `hash` (modo de prueba sin red) |
| `LLM` | Solo Python (servidor local) | `fallback` | `fallback` `gemini` `groq` `echo` |
| `TOP_K` | Python y Netlify | `5` | Fragmentos recuperados por consulta |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Solo Python (ingesta) | `900` / `150` | Tamaño y solapamiento de los trozos de texto |
| `OCR_ENABLED` | Solo Python (ingesta) | `true` | Activa el OCR para páginas sin texto extraíble |
| `OCR_LANG` | Solo Python (ingesta) | `spa+eng` | Idiomas para el OCR |

---

## Ejemplos de preguntas y respuestas

Con los documentos de ejemplo incluidos en `data/ejemplo/` (un
reglamento académico, una malla curricular y un PDF-escaneo simulado
sobre becas — todos ficticios, pensados solo para poder probar el
agente sin exponer documentos reales de ninguna universidad):

| Pregunta | Respuesta del agente |
|---|---|
| ¿Cuál es el promedio mínimo para aprobar una materia? | El promedio mínimo de aprobación es 6.0 sobre 10.0 [1]. Entre 4.0 y 5.9 hay derecho a examen de recuperación; por debajo de 4.0 la materia debe cursarse de nuevo [1]. |
| ¿Cuántas horas de prácticas profesionales se necesitan para titularse? | Se requieren 300 horas de prácticas profesionales, además de aprobar el 100% de las materias del plan de estudios y defender un proyecto de titulación ante un comité de al menos 3 profesores [1][2]. |
| ¿Qué cubre la beca deportiva? | La beca deportiva cubre el 50% del arancel semestral, y se debe mantener un promedio mínimo de 7.0 para conservarla [4]. |
| ¿Qué pasa si falto a clases por motivos de salud? | Se justifica presentando un certificado médico dentro de los 5 días hábiles posteriores a la falta [1]. |
| ¿Cuál es la capital de Australia? | No encontré esa información en los documentos disponibles. |

El último caso es el que más importa: el agente está instruido para
decir cuándo algo **no** está en los documentos, en vez de contestarlo
de memoria.

> Nota: estos ejemplos muestran el formato real de respuesta (incluida
> la forma de citar `[n]`); fueron redactados a partir del contenido de
> `data/ejemplo/` para ilustrar el comportamiento esperado. Al correr el
> proyecto con tu propia `GEMINI_API_KEY`, las respuestas se generan en
> vivo con esos mismos documentos.

---

## ☁️ Evidencia del deploy

_Pendiente de completar tras desplegar siguiendo `deploy/GUIA_NETLIFY.md`._

- **Enlace público:** `https://<tu-sitio>.netlify.app`
- **Captura de pantalla / video:**

  <!-- Reemplaza esta línea por la imagen o el video, por ejemplo: -->
  <!-- ![Asesor UNI corriendo en Netlify](docs/deploy-evidence.png) -->

---

## Estructura del repositorio

```
uni-agente/
├── app/                      Backend Python: ingesta + servidor local
│   ├── config.py               Configuración por variables de entorno
│   ├── loaders.py               PDF (+OCR), TXT, MD, CSV → Passage
│   ├── chunking.py              Troceado por oración con solapamiento
│   ├── embeddings.py            Embedder: gemini | hash
│   ├── vectorstore.py           Índice en JSON (chunks + vectores)
│   ├── llm.py                   LLMClient: fallback | gemini | groq | echo
│   ├── agent.py                 Recuperación, prompt, citas
│   ├── ingest.py                Construcción del índice
│   └── api.py                   FastAPI (servidor local)
├── netlify/functions/         Backend Node: lo que corre en producción
│   ├── ask.js                   Equivalente de agent.py + llm.py + embeddings.py
│   ├── health.js
│   ├── diagnostico.js
│   └── data/index.json          Índice commiteado (el que usa Netlify)
├── web/                       Frontend sin framework
│   ├── index.html
│   └── assets/ (style.css, script.js)
├── deploy/
│   ├── GUIA_NETLIFY.md          Guía paso a paso del deploy (recomendado)
│   ├── setup.sh                 Alternativa: aprovisionamiento en OCI
│   └── GUIA_OCI.md               Alternativa: guía paso a paso en OCI
├── data/
│   ├── ejemplo/                  Documentos ficticios para probar el agente
│   └── README.md                 Cómo cargar tus documentos reales
├── netlify.toml                Config de Netlify (publish, functions, redirects)
├── package.json
├── .env.example
├── requirements.txt
└── README.md
```

## Licencia

MIT.


#NOTA

Sobre la integridad del historial de control de versiones:
Durante la fase de integración, el repositorio experimentó un incidente de exposición de credenciales (GH013). En el proceso de remediación técnica y sanitización del árbol de trabajo, se ejecutó una reinicialización de la base de datos local de Git para purgar criptográficamente el secreto expuesto. Por este motivo, el historial de commits previo a la resolución de la vulnerabilidad no se encuentra reflejado en la rama principal actual.

#Evidencia
Este es el video de evidencia de que la app funcionó localmente


https://github.com/user-attachments/assets/5e8e08e1-f9c6-4f3c-91d5-8e088075b412






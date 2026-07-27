# Guía: desplegar en Netlify desde cero

10-15 minutos, sin costo (plan gratuito de Netlify es más que suficiente
para este proyecto).

## 0. Antes de desplegar: genera el índice

Netlify no corre Python en producción (ver por qué en el `README.md`,
sección Arquitectura), así que el índice se genera **antes** de
desplegar, en tu máquina, y se sube al repositorio ya construido.

```bash
# con tus documentos reales en data/, o con los de ejemplo:
cp data/ejemplo/* data/

python -m app.ingest              # crea index/index.json
cp index/index.json netlify/functions/data/index.json

git add netlify/functions/data/index.json
git commit -m "data: índice para el deploy en Netlify"
git push
```

Si no haces este paso, el sitio igual se despliega y el link funciona,
pero el agente va a responder "todavía no hay documentos indexados" —
es un colchón de seguridad, no un error.

## 1. Crear la cuenta y conectar el repositorio

1. Entra a [app.netlify.com](https://app.netlify.com) y crea una cuenta
   (puedes registrarte directo con tu cuenta de GitHub, es lo más
   rápido).
2. Clic en **Add new site → Import an existing project**.
3. Elige **GitHub** y autoriza a Netlify a acceder a tus repositorios
   (puedes limitarlo a solo este repo si prefieres).
4. Busca y selecciona tu repositorio `uni-agente`.

## 2. Configuración de build

Netlify va a detectar automáticamente el archivo `netlify.toml` del
repo y va a proponer:

- **Base directory:** (vacío)
- **Build command:** (vacío — no hay paso de build, son archivos estáticos)
- **Publish directory:** `web`
- **Functions directory:** `netlify/functions`

No necesitas cambiar nada de esto; el `netlify.toml` ya lo trae
configurado. Solo revisa que aparezca así antes de continuar.

## 3. Variables de entorno

Antes de darle a "Deploy" (o inmediatamente después, y luego rehaces el
deploy):

1. **Site configuration → Environment variables → Add a variable → Add a single variable**.
2. Agrega:
   - `GEMINI_API_KEY` = tu key de [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
   - `GROQ_API_KEY` = tu key de [console.groq.com/keys](https://console.groq.com/keys) (opcional, pero recomendada)
3. En **Scopes**, asegúrate de que quede marcado **Functions** (es el
   scope que hace que `ask.js` pueda leer la variable en tiempo real).

## 4. Deploy

Clic en **Deploy site**. Toma 1-2 minutos. Cuando termine, Netlify te da
una URL tipo `https://nombre-aleatorio-123abc.netlify.app`.

Si agregaste las variables de entorno *después* del primer deploy, ve a
**Deploys → Trigger deploy → Deploy site** para que las tome en cuenta.

## 5. (Opcional) Cambiar el nombre del subdominio

**Site configuration → General → Site details → Change site name**, para
tener algo tipo `https://asesor-uni.netlify.app` en vez del nombre
aleatorio.

## 6. Verificar que quedó arriba

1. Abre tu URL — deberías ver la interfaz del agente, con el punto de
   estado (arriba a la derecha) en verde.
2. Haz una pregunta de prueba (si usaste los documentos de ejemplo,
   prueba "¿cuál es el promedio mínimo para aprobar?").
3. Si algo falla, revisa los logs: en el dashboard de Netlify, ve a
   **Logs → Functions → ask** para ver el error exacto (casi siempre es
   una API key mal copiada o sin el scope "Functions").

## 7. Evidencia para el README del challenge

Con el agente respondiendo en `https://tu-sitio.netlify.app`, toma una
captura de pantalla (o un video corto haciendo una pregunta) y agrégala
en la sección "Evidencia del deploy" del `README.md` principal, junto
con el enlace.

## ¿Y si actualizo mis documentos después?

Cada vez que cambies algo en `data/`:

```bash
python -m app.ingest
cp index/index.json netlify/functions/data/index.json
git add netlify/functions/data/index.json
git commit -m "data: actualizar índice"
git push
```

Netlify vuelve a desplegar automáticamente en cada push a la rama
principal (Continuous Deployment ya viene activado por defecto).

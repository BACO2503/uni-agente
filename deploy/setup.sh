#!/usr/bin/env bash
#
# Aprovisiona una VM de Oracle Cloud Infrastructure (Compute, Always Free)
# para correr el Asesor UNI de forma permanente, con HTTPS automático.
#
# Uso, ya dentro de la VM (Ubuntu 22.04/24.04, x86 o ARM):
#   git clone <tu-repo> ~/uni-agente && cd ~/uni-agente
#   cp .env.example .env && nano .env      # pega tus API keys
#   sudo bash deploy/setup.sh
#
# Al terminar, el agente queda accesible en:
#   https://<ip-publica-de-la-vm>.sslip.io
#
# IMPORTANTE: además de este script, en la consola web de OCI hay que
# abrir los puertos 80 y 443 manualmente (ver deploy/GUIA_OCI.md,
# sección "Abrir el firewall"). Sin esa regla el servidor responde en
# localhost pero no desde internet.

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER="${SUDO_USER:-$(whoami)}"
SERVICE_NAME="uni-agente"
PORT="$(grep -E '^PORT=' "$APP_DIR/.env" 2>/dev/null | cut -d= -f2)"
PORT="${PORT:-8000}"

echo "==> Directorio del proyecto: $APP_DIR"
echo "==> Usuario de servicio: $APP_USER"
echo "==> Puerto interno: $PORT"

echo "==> Instalando dependencias del sistema (Python, OCR, Caddy)..."
apt-get update -y
apt-get install -y \
  python3-venv python3-pip \
  tesseract-ocr tesseract-ocr-spa \
  poppler-utils \
  curl gnupg debian-keyring debian-archive-keyring apt-transport-https

# --- Caddy: reverse proxy con TLS automático (Let's Encrypt) ---
if ! command -v caddy >/dev/null 2>&1; then
  echo "==> Instalando Caddy..."
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
fi

# --- Entorno virtual de Python + dependencias del proyecto ---
echo "==> Creando entorno virtual e instalando dependencias..."
cd "$APP_DIR"
python3 -m venv .venv
"$APP_DIR/.venv/bin/pip" install --upgrade pip -q
"$APP_DIR/.venv/bin/pip" install -r requirements.txt -q

if [ ! -f "$APP_DIR/.env" ]; then
  echo "!! No hay archivo .env. Copia .env.example a .env y agrega tus API keys antes de continuar."
  exit 1
fi

# --- Ingesta inicial (si hay documentos en data/) ---
echo "==> Corriendo ingesta de documentos..."
"$APP_DIR/.venv/bin/python" -m app.ingest || echo "Aviso: ingesta falló o no hay documentos aún; puedes correrla después."

# --- Servicio systemd: mantiene el agente corriendo y lo reinicia si falla ---
echo "==> Registrando servicio systemd..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Asesor UNI - agente de IA documental
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/uvicorn app.api:app --host 127.0.0.1 --port ${PORT}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

# --- Caddy: obtiene el certificado TLS y hace de proxy hacia uvicorn ---
PUBLIC_IP="$(curl -s -4 ifconfig.me || curl -s -4 icanhazip.com)"
DOMAIN="${PUBLIC_IP}.sslip.io"
echo "==> Configurando Caddy para ${DOMAIN}..."

cat > /etc/caddy/Caddyfile <<EOF
${DOMAIN} {
    reverse_proxy 127.0.0.1:${PORT}
}
EOF

systemctl restart caddy

echo ""
echo "======================================================================"
echo " Listo. El agente debería quedar disponible en unos segundos en:"
echo "   https://${DOMAIN}"
echo ""
echo " Revisa el estado con:"
echo "   sudo systemctl status ${SERVICE_NAME}"
echo "   sudo journalctl -u ${SERVICE_NAME} -f"
echo ""
echo " Recuerda abrir los puertos 80 y 443 en la Security List de tu VCN"
echo " en la consola de OCI (ver deploy/GUIA_OCI.md) si todavía no lo hiciste."
echo "======================================================================"

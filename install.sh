#!/bin/bash
# =============================================================================
# Podman Kube Generator — Installations-Script
# =============================================================================
set -e

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="podman-kube-gen"
SERVICE_NAME="${APP_NAME}.service"
MIN_PYTHON="3.10"

# ── Farben ────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
info() { echo -e "${CYAN}  →${NC} $*"; }
warn() { echo -e "${YELLOW}  !${NC} $*"; }
err()  { echo -e "${RED}  ✗${NC} $*"; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     Podman Kube Generator — Installation     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Python-Version prüfen ─────────────────────────────────────────
info "Prüfe Python-Version..."
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=${version%%.*}; minor=${version##*.}
        if [[ $major -ge 3 && $minor -ge 10 ]]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done
if [[ -z "$PYTHON_BIN" ]]; then
    err "Python ${MIN_PYTHON}+ nicht gefunden. Bitte installieren und erneut ausführen."
    exit 1
fi
ok "Python $($PYTHON_BIN --version) gefunden ($PYTHON_BIN)"

# ── venv erstellen / aktualisieren ────────────────────────────────
VENV_DIR="${INSTALL_DIR}/venv"
if [[ -d "$VENV_DIR" ]]; then
    info "Vorhandenes venv wird aktualisiert..."
else
    info "Erstelle Python venv..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
ok "venv: ${VENV_DIR}"

PIP="${VENV_DIR}/bin/pip"
PYTHON="${VENV_DIR}/bin/python"
MANAGE="${VENV_DIR}/bin/python ${INSTALL_DIR}/manage.py"

info "Installiere Abhängigkeiten..."
"$PIP" install -q --upgrade pip
"$PIP" install -q -r "${INSTALL_DIR}/requirements.txt"
ok "Abhängigkeiten installiert"

# ── .env einrichten ───────────────────────────────────────────────
ENV_FILE="${INSTALL_DIR}/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    info "Erstelle .env..."
    SECRET_KEY=$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe(50))")

    echo ""
    echo -e "${YELLOW}Konfiguration:${NC}"
    read -rp "  Domain/URL der App (z.B. https://podman.example.com): " SITE_URL_INPUT
    SITE_URL_INPUT="${SITE_URL_INPUT:-http://localhost:8000}"
    SITE_URL_INPUT="${SITE_URL_INPUT%/}"  # trailing slash entfernen

    # ALLOWED_HOSTS aus URL ableiten
    HOST=$(echo "$SITE_URL_INPUT" | sed 's|https\?://||' | sed 's|/.*||' | sed 's|:.*||')
    ALLOWED_HOSTS="localhost,127.0.0.1,${HOST}"

    cat > "$ENV_FILE" <<EOF
DJANGO_SECRET_KEY=${SECRET_KEY}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${ALLOWED_HOSTS}
SITE_URL=${SITE_URL_INPUT}
EOF
    ok ".env erstellt (SECRET_KEY generiert)"
else
    warn ".env bereits vorhanden — wird nicht überschrieben"
fi

# ── Datenbank & statische Dateien ─────────────────────────────────
cd "$INSTALL_DIR"

info "Führe Migrationen durch..."
$MANAGE migrate --run-syncdb -v 0
ok "Datenbank migriert"

info "Importiere Stacks..."
$MANAGE load_stacks
ok "Stacks importiert"

info "Sammle statische Dateien..."
$MANAGE collectstatic --noinput -v 0
ok "Statische Dateien gesammelt"

# ── Standard-Admin anlegen (admin/admin) ──────────────────────────
$MANAGE shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@localhost', 'admin')
    print('  Superuser admin/admin angelegt')
else:
    print('  admin existiert bereits')
"
warn "Standard-Login: admin / admin — bitte im Admin-Bereich ändern!"

# ── Systemd User-Service einrichten ──────────────────────────────
echo ""
read -rp "Systemd User-Service einrichten? (autostart beim Login) [J/n]: " SETUP_SYSTEMD
SETUP_SYSTEMD="${SETUP_SYSTEMD:-J}"

if [[ "${SETUP_SYSTEMD,,}" == "j" || "${SETUP_SYSTEMD,,}" == "y" ]]; then
    read -rp "  Port für Gunicorn [8000]: " GUNICORN_PORT
    GUNICORN_PORT="${GUNICORN_PORT:-8000}"
    read -rp "  Anzahl Gunicorn Worker [2]: " GUNICORN_WORKERS
    GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"

    SYSTEMD_DIR="${HOME}/.config/systemd/user"
    mkdir -p "$SYSTEMD_DIR"

    cat > "${SYSTEMD_DIR}/${SERVICE_NAME}" <<EOF
[Unit]
Description=Podman Kube Generator
After=network.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_DIR}/bin/gunicorn config.wsgi:application \\
    --bind 127.0.0.1:${GUNICORN_PORT} \\
    --workers ${GUNICORN_WORKERS} \\
    --timeout 60 \\
    --access-logfile - \\
    --error-logfile -
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable "${SERVICE_NAME}"
    systemctl --user start "${SERVICE_NAME}"

    sleep 1
    if systemctl --user is-active --quiet "${SERVICE_NAME}"; then
        ok "Service läuft auf 127.0.0.1:${GUNICORN_PORT}"
    else
        warn "Service gestartet — Status prüfen mit: systemctl --user status ${SERVICE_NAME}"
    fi

    # Linger aktivieren (Service überlebt Logout)
    if command -v loginctl &>/dev/null; then
        loginctl enable-linger "$(whoami)" 2>/dev/null && ok "loginctl enable-linger aktiviert (autostart ohne Login)"
    fi
fi

# ── Zusammenfassung ───────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           Installation abgeschlossen!        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  App-Verzeichnis:  ${CYAN}${INSTALL_DIR}${NC}"
if [[ "${SETUP_SYSTEMD,,}" == "j" || "${SETUP_SYSTEMD,,}" == "y" ]]; then
echo -e "  Service:          ${CYAN}systemctl --user status ${SERVICE_NAME}${NC}"
echo -e "  Logs:             ${CYAN}journalctl --user -u ${SERVICE_NAME} -f${NC}"
echo -e "  Neustart:         ${CYAN}systemctl --user restart ${SERVICE_NAME}${NC}"
else
echo -e "  Starten:          ${CYAN}cd ${INSTALL_DIR} && ./start.sh${NC}"
fi
echo ""
echo -e "  Admin:            ${CYAN}http://localhost:${GUNICORN_PORT:-8000}/admin/${NC}"
echo ""
if [[ "${SETUP_SYSTEMD,,}" == "j" || "${SETUP_SYSTEMD,,}" == "y" ]]; then
echo -e "${YELLOW}  Nginx Reverse-Proxy Beispiel:${NC}"
echo -e "  location / {"
echo -e "      proxy_pass http://127.0.0.1:${GUNICORN_PORT};"
echo -e "      proxy_set_header Host \$host;"
echo -e "      proxy_set_header X-Real-IP \$remote_addr;"
echo -e "  }"
echo ""
fi

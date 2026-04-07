#!/bin/bash
# =============================================================================
# Podman Kube Generator — Installation Script
# =============================================================================
set -e

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="podman-kube-gen"
SERVICE_NAME="${APP_NAME}.service"
MIN_PYTHON="3.10"

# ── Colors ────────────────────────────────────────────────────────
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

# ── Python version check ──────────────────────────────────────────
info "Checking Python version..."
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
    err "Python ${MIN_PYTHON}+ not found. Please install it and try again."
    exit 1
fi
ok "Python $($PYTHON_BIN --version) found ($PYTHON_BIN)"

# ── Create / update venv ──────────────────────────────────────────
VENV_DIR="${INSTALL_DIR}/venv"
if [[ -d "$VENV_DIR" ]]; then
    info "Updating existing venv..."
else
    info "Creating Python venv..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
ok "venv: ${VENV_DIR}"

PIP="${VENV_DIR}/bin/pip"
PYTHON="${VENV_DIR}/bin/python"
MANAGE="${VENV_DIR}/bin/python ${INSTALL_DIR}/manage.py"

info "Installing dependencies..."
"$PIP" install -q --upgrade pip
"$PIP" install -q -r "${INSTALL_DIR}/requirements.txt"
ok "Dependencies installed"

# ── .env setup ───────────────────────────────────────────────────
ENV_FILE="${INSTALL_DIR}/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    info "Creating .env..."
    SECRET_KEY=$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe(50))")

    echo ""
    echo -e "${YELLOW}Configuration:${NC}"
    read -rp "  App domain/URL (e.g. https://podman.example.com): " SITE_URL_INPUT
    SITE_URL_INPUT="${SITE_URL_INPUT:-http://localhost:8000}"
    SITE_URL_INPUT="${SITE_URL_INPUT%/}"

    HOST=$(echo "$SITE_URL_INPUT" | sed 's|https\?://||' | sed 's|/.*||' | sed 's|:.*||')
    ALLOWED_HOSTS="localhost,127.0.0.1,${HOST}"

    cat > "$ENV_FILE" <<EOF
DJANGO_SECRET_KEY=${SECRET_KEY}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${ALLOWED_HOSTS}
SITE_URL=${SITE_URL_INPUT}
CSRF_TRUSTED_ORIGINS=${SITE_URL_INPUT}
EOF
    ok ".env created (SECRET_KEY generated)"
else
    warn ".env already exists — skipping"
fi

# ── Database & static files ───────────────────────────────────────
cd "$INSTALL_DIR"

info "Running migrations..."
$MANAGE migrate --run-syncdb -v 0
ok "Database migrated"

info "Importing stacks..."
$MANAGE load_stacks
ok "Stacks imported"

info "Collecting static files..."
$MANAGE collectstatic --noinput -v 0
ok "Static files collected"

# ── Create default admin (admin/admin) ───────────────────────────
$MANAGE shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@localhost', 'admin')
    print('  Superuser admin/admin created')
else:
    print('  admin already exists')
"
warn "Default login: admin / admin — please change this in the admin panel!"

# ── Systemd user service ──────────────────────────────────────────
echo ""
read -rp "Set up systemd user service (autostart on login)? [Y/n]: " SETUP_SYSTEMD
SETUP_SYSTEMD="${SETUP_SYSTEMD:-Y}"

if [[ "${SETUP_SYSTEMD,,}" == "y" || "${SETUP_SYSTEMD,,}" == "j" ]]; then
    read -rp "  Gunicorn port [8000]: " GUNICORN_PORT
    GUNICORN_PORT="${GUNICORN_PORT:-8000}"
    read -rp "  Gunicorn workers [2]: " GUNICORN_WORKERS
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
        ok "Service running on 127.0.0.1:${GUNICORN_PORT}"
    else
        warn "Service started — check status with: systemctl --user status ${SERVICE_NAME}"
    fi

    if command -v loginctl &>/dev/null; then
        loginctl enable-linger "$(whoami)" 2>/dev/null && ok "loginctl enable-linger enabled (autostart without login)"
    fi
fi

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          Installation complete!              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  App directory:  ${CYAN}${INSTALL_DIR}${NC}"
if [[ "${SETUP_SYSTEMD,,}" == "y" || "${SETUP_SYSTEMD,,}" == "j" ]]; then
echo -e "  Service:        ${CYAN}systemctl --user status ${SERVICE_NAME}${NC}"
echo -e "  Logs:           ${CYAN}journalctl --user -u ${SERVICE_NAME} -f${NC}"
echo -e "  Restart:        ${CYAN}systemctl --user restart ${SERVICE_NAME}${NC}"
else
echo -e "  Start:          ${CYAN}cd ${INSTALL_DIR} && ./start.sh${NC}"
fi
echo ""
echo -e "  Admin:          ${CYAN}http://localhost:${GUNICORN_PORT:-8000}/admin/${NC}"
echo ""
if [[ "${SETUP_SYSTEMD,,}" == "y" || "${SETUP_SYSTEMD,,}" == "j" ]]; then
echo -e "${YELLOW}  Nginx reverse proxy example:${NC}"
echo -e "  location / {"
echo -e "      proxy_pass http://127.0.0.1:${GUNICORN_PORT};"
echo -e "      proxy_set_header Host \$host;"
echo -e "      proxy_set_header X-Real-IP \$remote_addr;"
echo -e "  }"
echo ""
fi

#!/bin/bash
# =============================================================================
# Podman Kube Generator — Deploy Script
# Sets up the app on a fresh Debian 13 server
# Run as root: bash deploy.sh /path/to/podman-kube-gen_*.tar.gz
# =============================================================================
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────
APP_USER="generator"
APP_DIR="/home/$APP_USER/podman-kube-gen"
SERVICE_NAME="podman-kube-gen.service"
PACKAGE="${1:-}"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
info() { echo -e "${CYAN}  →${NC} $*"; }
warn() { echo -e "${YELLOW}  !${NC} $*"; }
err()  { echo -e "${RED}  ✗${NC} $*"; exit 1; }
step() { echo -e "\n${BOLD}$*${NC}"; }

echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║    Podman Kube Generator — Deploy Script     ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Preflight ──────────────────────────────────────────────────
step "── Preflight check ─────────────────────────────────────"

[[ $EUID -eq 0 ]] || err "Please run as root: sudo bash deploy.sh ..."
[[ -n "$PACKAGE" ]] || err "No package specified. Usage: bash deploy.sh /path/to/package.tar.gz"
[[ -f "$PACKAGE" ]] || err "Package not found: $PACKAGE"

ok "Running as root"
ok "Package found: $PACKAGE ($(du -h "$PACKAGE" | cut -f1))"

# ── Configuration input ────────────────────────────────────────
step "── Configuration ───────────────────────────────────────"

echo ""
read -rp "  App domain/URL (e.g. https://podman.example.com): " SITE_URL
SITE_URL="${SITE_URL%/}"
[[ -n "$SITE_URL" ]] || err "No URL specified."

read -rp "  Gunicorn port [9500]: " APP_PORT
APP_PORT="${APP_PORT:-9500}"

read -rp "  Configure Nginx? [Y/n]: " SETUP_NGINX
SETUP_NGINX="${SETUP_NGINX:-Y}"

read -rp "  Gunicorn workers [2]: " WORKERS
WORKERS="${WORKERS:-2}"

DOMAIN=$(echo "$SITE_URL" | sed 's|https\?://||' | sed 's|/.*||')

echo ""
info "Domain:   $DOMAIN"
info "Port:     $APP_PORT"
info "Workers:  $WORKERS"
info "Nginx:    $([[ "${SETUP_NGINX,,}" =~ ^[jy] ]] && echo yes || echo no)"
echo ""
read -rp "$(echo -e "${YELLOW}  Correct? Proceed? [y/N]:${NC} ")" confirm
[[ "${confirm,,}" =~ ^[jy] ]] || { warn "Cancelled."; exit 0; }

# ── System packages ────────────────────────────────────────────
step "── Installing system packages ──────────────────────────"

info "apt update..."
apt-get update -qq

PACKAGES=(
    python3
    python3-venv
    python3-pip
    python3-dev
    # Pillow dependencies
    libjpeg-dev
    libpng-dev
    zlib1g-dev
    libwebp-dev
    # Other
    curl
    tar
    sqlite3
)

[[ "${SETUP_NGINX,,}" =~ ^[jy] ]] && PACKAGES+=(nginx certbot python3-certbot-nginx)

info "Installing: ${PACKAGES[*]}"
apt-get install -y -qq "${PACKAGES[@]}"
ok "System packages installed."

# ── Create user ────────────────────────────────────────────────
step "── Setting up user ─────────────────────────────────────"

if id "$APP_USER" &>/dev/null; then
    warn "User '$APP_USER' already exists."
else
    useradd -m -s /bin/bash "$APP_USER"
    ok "User '$APP_USER' created."
fi

loginctl enable-linger "$APP_USER"
ok "loginctl enable-linger enabled."

# ── Extract app ────────────────────────────────────────────────
step "── Extracting application ──────────────────────────────"

if [[ -d "$APP_DIR" ]]; then
    warn "Target directory already exists: $APP_DIR"
    read -rp "  Overwrite? Existing data will be lost! [y/N]: " overwrite
    [[ "${overwrite,,}" =~ ^[jy] ]] || err "Cancelled."
    rm -rf "$APP_DIR"
fi

mkdir -p "/home/$APP_USER"
info "Extracting to /home/$APP_USER/..."
tar -xzf "$PACKAGE" -C "/home/$APP_USER/"

EXTRACTED_DIR=$(tar -tzf "$PACKAGE" | head -1 | cut -d/ -f1)
if [[ "$EXTRACTED_DIR" != "podman-kube-gen" ]]; then
    mv "/home/$APP_USER/$EXTRACTED_DIR" "$APP_DIR"
fi

chown -R "$APP_USER:$APP_USER" "/home/$APP_USER"
ok "Application extracted to: $APP_DIR"

# ── Configure .env ─────────────────────────────────────────────
step "── Configuring environment ─────────────────────────────"

ENV_FILE="$APP_DIR/.env"
[[ -f "$ENV_FILE" ]] || err ".env not found in package."

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
ALLOWED_HOSTS="localhost,127.0.0.1,$DOMAIN"

update_env() {
    local key="$1" val="$2"
    if grep -q "^${key}=" "$ENV_FILE"; then
        sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
    else
        echo "${key}=${val}" >> "$ENV_FILE"
    fi
}

update_env "DJANGO_SECRET_KEY" "$SECRET_KEY"
update_env "DJANGO_DEBUG" "False"
update_env "DJANGO_ALLOWED_HOSTS" "$ALLOWED_HOSTS"
update_env "SITE_URL" "$SITE_URL"
update_env "CSRF_TRUSTED_ORIGINS" "$SITE_URL"

chown "$APP_USER:$APP_USER" "$ENV_FILE"
chmod 600 "$ENV_FILE"
ok ".env updated (new SECRET_KEY generated)."

# ── Python venv ────────────────────────────────────────────────
step "── Setting up Python venv ──────────────────────────────"

info "Creating venv..."
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"

info "Installing dependencies..."
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
ok "Python dependencies installed."

# ── Django setup ───────────────────────────────────────────────
step "── Setting up Django ───────────────────────────────────"

MANAGE="sudo -u $APP_USER $APP_DIR/venv/bin/python $APP_DIR/manage.py"

info "Running migrations..."
$MANAGE migrate --run-syncdb -v 0
ok "Database migrated."

info "Importing stacks..."
$MANAGE load_stacks
ok "Stacks imported."

info "Collecting static files..."
$MANAGE collectstatic --noinput -v 0
ok "Static files collected."

# ── Systemd user service ───────────────────────────────────────
step "── Setting up systemd service ──────────────────────────"

SYSTEMD_DIR="/home/$APP_USER/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"

cat > "$SYSTEMD_DIR/$SERVICE_NAME" << EOF
[Unit]
Description=Podman Kube Generator
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/gunicorn config.wsgi:application \\
    --bind 127.0.0.1:${APP_PORT} \\
    --workers ${WORKERS} \\
    --timeout 60 \\
    --access-logfile - \\
    --error-logfile -
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

chown -R "$APP_USER:$APP_USER" "/home/$APP_USER/.config"

sudo -u "$APP_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $APP_USER)" \
    systemctl --user daemon-reload
sudo -u "$APP_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $APP_USER)" \
    systemctl --user enable "$SERVICE_NAME"
sudo -u "$APP_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $APP_USER)" \
    systemctl --user start "$SERVICE_NAME"

sleep 2
if sudo -u "$APP_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $APP_USER)" \
    systemctl --user is-active --quiet "$SERVICE_NAME"; then
    ok "Service running on 127.0.0.1:$APP_PORT"
else
    err "Service failed to start. Check with: journalctl --user -u $SERVICE_NAME -n 50"
fi

# ── Nginx ──────────────────────────────────────────────────────
if [[ "${SETUP_NGINX,,}" =~ ^[jy] ]]; then
    step "── Configuring Nginx ───────────────────────────────────"

    NGINX_CONF="/etc/nginx/sites-available/podman-kube-gen"

    cat > "$NGINX_CONF" << EOF
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 10M;

    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias $APP_DIR/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60;
    }
}
EOF

    ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/podman-kube-gen
    rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
    nginx -t && systemctl reload nginx
    ok "Nginx configured for $DOMAIN"

    echo ""
    read -rp "  Set up Let's Encrypt SSL certificate? [Y/n]: " SETUP_SSL
    SETUP_SSL="${SETUP_SSL:-Y}"
    if [[ "${SETUP_SSL,,}" =~ ^[jy] ]]; then
        read -rp "  Email for Let's Encrypt: " LE_EMAIL
        certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$LE_EMAIL"
        ok "SSL certificate installed."
    fi
fi

# ── Summary ────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║          Deployment complete! ✓              ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  App directory:  ${CYAN}$APP_DIR${NC}"
echo -e "  Service:        ${CYAN}journalctl --user -u $SERVICE_NAME -f${NC}"
echo -e "                  ${CYAN}(run as user '$APP_USER')${NC}"
echo -e "  URL:            ${CYAN}$SITE_URL${NC}"
echo -e "  Admin:          ${CYAN}$SITE_URL/admin/${NC}"
echo ""
warn "Admin password carried over from old server (DB was migrated)."
warn "Check firewall: open ports 80/443."
echo ""

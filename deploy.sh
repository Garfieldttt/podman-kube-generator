#!/bin/bash
# =============================================================================
# Podman Kube Generator — Deploy Script
# Richtet die App auf einem frischen Debian 13 Server ein
# Ausführen als root: bash deploy.sh /pfad/zu/podman-kube-gen_*.tar.gz
# =============================================================================
set -euo pipefail

# ── Konfiguration ──────────────────────────────────────────────
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

# ── Voraussetzungen ────────────────────────────────────────────
step "── Voraussetzungen prüfen ──────────────────────────────"

[[ $EUID -eq 0 ]] || err "Bitte als root ausführen: sudo bash deploy.sh ..."
[[ -n "$PACKAGE" ]] || err "Kein Paket angegeben. Verwendung: bash deploy.sh /pfad/zu/paket.tar.gz"
[[ -f "$PACKAGE" ]] || err "Paket nicht gefunden: $PACKAGE"

ok "Root-Rechte vorhanden"
ok "Paket gefunden: $PACKAGE ($(du -h "$PACKAGE" | cut -f1))"

# ── Konfigurationsabfrage ──────────────────────────────────────
step "── Konfiguration ───────────────────────────────────────"

echo ""
read -rp "  Domain/URL der App (z.B. https://podman.example.com): " SITE_URL
SITE_URL="${SITE_URL%/}"
[[ -n "$SITE_URL" ]] || err "Keine URL angegeben."

read -rp "  Gunicorn Port [9500]: " APP_PORT
APP_PORT="${APP_PORT:-9500}"

read -rp "  Nginx konfigurieren? [J/n]: " SETUP_NGINX
SETUP_NGINX="${SETUP_NGINX:-J}"

read -rp "  Gunicorn Worker [2]: " WORKERS
WORKERS="${WORKERS:-2}"

# Domain aus URL ableiten
DOMAIN=$(echo "$SITE_URL" | sed 's|https\?://||' | sed 's|/.*||')

echo ""
info "Domain:    $DOMAIN"
info "App-Port:  $APP_PORT"
info "Workers:   $WORKERS"
info "Nginx:     $([[ "${SETUP_NGINX,,}" =~ ^[jy] ]] && echo ja || echo nein)"
echo ""
read -rp "$(echo -e "${YELLOW}  Korrekt? Fortfahren? [j/N]:${NC} ")" confirm
[[ "${confirm,,}" =~ ^[jy] ]] || { warn "Abgebrochen."; exit 0; }

# ── System-Pakete ──────────────────────────────────────────────
step "── System-Pakete installieren ──────────────────────────"

info "apt update..."
apt-get update -qq

PACKAGES=(
    python3
    python3-venv
    python3-pip
    python3-dev
    # Pillow-Abhängigkeiten
    libjpeg-dev
    libpng-dev
    zlib1g-dev
    libwebp-dev
    # Sonstiges
    curl
    tar
    sqlite3
)

[[ "${SETUP_NGINX,,}" =~ ^[jy] ]] && PACKAGES+=(nginx certbot python3-certbot-nginx)

info "Installiere: ${PACKAGES[*]}"
apt-get install -y -qq "${PACKAGES[@]}"
ok "System-Pakete installiert."

# ── User anlegen ───────────────────────────────────────────────
step "── Benutzer einrichten ─────────────────────────────────"

if id "$APP_USER" &>/dev/null; then
    warn "Benutzer '$APP_USER' existiert bereits."
else
    useradd -m -s /bin/bash "$APP_USER"
    ok "Benutzer '$APP_USER' angelegt."
fi

# Linger aktivieren (Service überlebt Logout)
loginctl enable-linger "$APP_USER"
ok "loginctl enable-linger aktiviert."

# ── App entpacken ──────────────────────────────────────────────
step "── Anwendung entpacken ─────────────────────────────────"

if [[ -d "$APP_DIR" ]]; then
    warn "Zielverzeichnis existiert bereits: $APP_DIR"
    read -rp "  Überschreiben? Bestehende Daten gehen verloren! [j/N]: " overwrite
    [[ "${overwrite,,}" =~ ^[jy] ]] || err "Abgebrochen."
    rm -rf "$APP_DIR"
fi

mkdir -p "/home/$APP_USER"
info "Entpacke nach /home/$APP_USER/..."
tar -xzf "$PACKAGE" -C "/home/$APP_USER/"

# Verzeichnisname aus Tarball ermitteln
EXTRACTED_DIR=$(tar -tzf "$PACKAGE" | head -1 | cut -d/ -f1)
if [[ "$EXTRACTED_DIR" != "podman-kube-gen" ]]; then
    mv "/home/$APP_USER/$EXTRACTED_DIR" "$APP_DIR"
fi

chown -R "$APP_USER:$APP_USER" "/home/$APP_USER"
ok "Anwendung entpackt nach: $APP_DIR"

# ── .env anpassen ──────────────────────────────────────────────
step "── Konfiguration anpassen ──────────────────────────────"

ENV_FILE="$APP_DIR/.env"
[[ -f "$ENV_FILE" ]] || err ".env nicht im Paket enthalten."

# Werte aktualisieren
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
ALLOWED_HOSTS="localhost,127.0.0.1,$DOMAIN"

# Bestehende Werte ersetzen oder ergänzen
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
ok ".env aktualisiert (neuer SECRET_KEY generiert)."

# ── Python venv ────────────────────────────────────────────────
step "── Python venv einrichten ──────────────────────────────"

info "Erstelle venv..."
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"

info "Installiere Abhängigkeiten..."
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
ok "Python-Abhängigkeiten installiert."

# ── Django einrichten ──────────────────────────────────────────
step "── Django einrichten ───────────────────────────────────"

MANAGE="sudo -u $APP_USER $APP_DIR/venv/bin/python $APP_DIR/manage.py"

info "Migrationen..."
$MANAGE migrate --run-syncdb -v 0
ok "Datenbank migriert."

info "Stacks importieren..."
$MANAGE load_stacks
ok "Stacks importiert."

info "Statische Dateien sammeln..."
$MANAGE collectstatic --noinput -v 0
ok "Statische Dateien gesammelt."

# ── Systemd User Service ───────────────────────────────────────
step "── Systemd Service einrichten ──────────────────────────"

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

# Service starten
sudo -u "$APP_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $APP_USER)" \
    systemctl --user daemon-reload
sudo -u "$APP_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $APP_USER)" \
    systemctl --user enable "$SERVICE_NAME"
sudo -u "$APP_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $APP_USER)" \
    systemctl --user start "$SERVICE_NAME"

sleep 2
if sudo -u "$APP_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $APP_USER)" \
    systemctl --user is-active --quiet "$SERVICE_NAME"; then
    ok "Service läuft auf 127.0.0.1:$APP_PORT"
else
    err "Service konnte nicht gestartet werden. Prüfen mit: journalctl --user -u $SERVICE_NAME -n 50"
fi

# ── Nginx ──────────────────────────────────────────────────────
if [[ "${SETUP_NGINX,,}" =~ ^[jy] ]]; then
    step "── Nginx konfigurieren ──────────────────────────────────"

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
    ok "Nginx konfiguriert für $DOMAIN"

    echo ""
    read -rp "  Let's Encrypt SSL-Zertifikat einrichten? [J/n]: " SETUP_SSL
    SETUP_SSL="${SETUP_SSL:-J}"
    if [[ "${SETUP_SSL,,}" =~ ^[jy] ]]; then
        read -rp "  E-Mail für Let's Encrypt: " LE_EMAIL
        certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$LE_EMAIL"
        ok "SSL-Zertifikat eingerichtet."
    fi
fi

# ── Zusammenfassung ────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║         Deployment abgeschlossen! ✓          ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  App-Verzeichnis:  ${CYAN}$APP_DIR${NC}"
echo -e "  Service:          ${CYAN}journalctl --user -u $SERVICE_NAME -f${NC}"
echo -e "                    ${CYAN}(als User '$APP_USER' ausführen)${NC}"
echo -e "  URL:              ${CYAN}$SITE_URL${NC}"
echo -e "  Admin:            ${CYAN}$SITE_URL/admin/${NC}"
echo ""
warn "Admin-Passwort aus dem alten Server übernommen (DB wurde migriert)."
warn "Firewall prüfen: Port 80/443 freigeben."
echo ""

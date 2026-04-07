#!/bin/bash
# =============================================================================
# Podman Kube Generator — Pack Script
# Erstellt ein vollständiges Migrations-Paket für den Umzug auf einen neuen Server
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PACKAGE_NAME="podman-kube-gen_${TIMESTAMP}.tar.gz"
PACKAGE_PATH="/tmp/$PACKAGE_NAME"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
info() { echo -e "${CYAN}  →${NC} $*"; }
warn() { echo -e "${YELLOW}  !${NC} $*"; }
err()  { echo -e "${RED}  ✗${NC} $*"; exit 1; }

echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║    Podman Kube Generator — Pack Script       ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Prüfen ─────────────────────────────────────────────────────
[[ -f "$SCRIPT_DIR/.env" ]]       || err ".env nicht gefunden"
[[ -f "$SCRIPT_DIR/db.sqlite3" ]] || err "db.sqlite3 nicht gefunden"
[[ -f "$SCRIPT_DIR/manage.py" ]]  || err "manage.py nicht gefunden"

# ── Paket erstellen ────────────────────────────────────────────
info "Erstelle Paket: $PACKAGE_NAME"

tar -czf "$PACKAGE_PATH" \
    --exclude="./.git" \
    --exclude="./venv" \
    --exclude="./staticfiles" \
    --exclude="./__pycache__" \
    --exclude="./.update-backup" \
    --exclude="./generator/__pycache__" \
    --exclude="./config/__pycache__" \
    --exclude="./**/__pycache__" \
    --exclude="*.pyc" \
    --exclude="*.pyo" \
    -C "$(dirname "$SCRIPT_DIR")" \
    "$(basename "$SCRIPT_DIR")"

SIZE=$(du -h "$PACKAGE_PATH" | cut -f1)
ok "Paket erstellt: $PACKAGE_PATH ($SIZE)"

echo ""
echo -e "${BOLD}  Enthält:${NC}"
echo -e "    • Anwendungscode"
echo -e "    • Datenbank (db.sqlite3)"
echo -e "    • Konfiguration (.env)"
[[ -d "$SCRIPT_DIR/media" ]] && echo -e "    • Media-Dateien (Avatare)"
echo -e "    • Migrations, Templates, Static-Quellen"
echo ""

# ── Hinweis ────────────────────────────────────────────────────
echo -e "${YELLOW}${BOLD}  Nächste Schritte:${NC}"
echo -e "  1. Paket auf neuen Server übertragen:"
echo -e "     ${CYAN}scp $PACKAGE_PATH root@NEUER-SERVER:/root/${NC}"
echo ""
echo -e "  2. deploy.sh auf neuen Server übertragen:"
echo -e "     ${CYAN}scp $SCRIPT_DIR/deploy.sh root@NEUER-SERVER:/root/${NC}"
echo ""
echo -e "  3. Auf neuem Server als root ausführen:"
echo -e "     ${CYAN}bash /root/deploy.sh /root/$PACKAGE_NAME${NC}"
echo ""

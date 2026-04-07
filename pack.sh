#!/bin/bash
# =============================================================================
# Podman Kube Generator — Pack Script
# Creates a complete migration package for moving to a new server
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

# ── Checks ─────────────────────────────────────────────────────
[[ -f "$SCRIPT_DIR/.env" ]]       || err ".env not found"
[[ -f "$SCRIPT_DIR/db.sqlite3" ]] || err "db.sqlite3 not found"
[[ -f "$SCRIPT_DIR/manage.py" ]]  || err "manage.py not found"

# ── Create package ─────────────────────────────────────────────
info "Creating package: $PACKAGE_NAME"

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
    --exclude="./~" \
    -C "$(dirname "$SCRIPT_DIR")" \
    "$(basename "$SCRIPT_DIR")"

SIZE=$(du -h "$PACKAGE_PATH" | cut -f1)
ok "Package created: $PACKAGE_PATH ($SIZE)"

echo ""
echo -e "${BOLD}  Contains:${NC}"
echo -e "    • Application code"
echo -e "    • Database (db.sqlite3)"
echo -e "    • Configuration (.env)"
[[ -d "$SCRIPT_DIR/media" ]] && echo -e "    • Media files (avatars)"
echo -e "    • Migrations, templates, static sources"
echo ""

# ── Next steps ─────────────────────────────────────────────────
echo -e "${YELLOW}${BOLD}  Next steps:${NC}"
echo -e "  1. Transfer package to new server:"
echo -e "     ${CYAN}scp $PACKAGE_PATH root@NEW-SERVER:/root/${NC}"
echo ""
echo -e "  2. Transfer deploy.sh to new server:"
echo -e "     ${CYAN}scp $SCRIPT_DIR/deploy.sh root@NEW-SERVER:/root/${NC}"
echo ""
echo -e "  3. Run on new server as root:"
echo -e "     ${CYAN}bash /root/deploy.sh /root/$PACKAGE_NAME${NC}"
echo ""

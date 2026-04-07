#!/bin/bash
# =============================================================================
# Podman Kube Generator — Update Script
# Checks compatibility, updates packages + DB, rolls back on failure
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"
MANAGE="$PYTHON $SCRIPT_DIR/manage.py"
SERVICE="podman-kube-gen.service"
DB="$SCRIPT_DIR/db.sqlite3"
BACKUP_DIR="$SCRIPT_DIR/.update-backup"
LOG="$BACKUP_DIR/update.log"

_PKGS_UPDATED=0
_DB_MIGRATED=0

# ── Colors ─────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'
BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*" | tee -a "$LOG"; }
info() { echo -e "${CYAN}  →${NC} $*" | tee -a "$LOG"; }
warn() { echo -e "${YELLOW}  !${NC} $*" | tee -a "$LOG"; }
err()  { echo -e "${RED}  ✗${NC} $*" | tee -a "$LOG"; }
step() { echo -e "\n${BOLD}$*${NC}" | tee -a "$LOG"; }

# ── Rollback ───────────────────────────────────────────────────
rollback() {
    local reason="$1"
    echo "" | tee -a "$LOG"
    echo -e "${RED}${BOLD}══════════════════════════════════════════════${NC}" | tee -a "$LOG"
    echo -e "${RED}  ROLLBACK: $reason${NC}" | tee -a "$LOG"
    echo -e "${RED}${BOLD}══════════════════════════════════════════════${NC}" | tee -a "$LOG"

    set +e

    if [[ $_DB_MIGRATED -eq 1 ]]; then
        warn "Restoring database..."
        if [[ -f "$BACKUP_DIR/db.sqlite3.bak" ]]; then
            cp "$BACKUP_DIR/db.sqlite3.bak" "$DB"
            ok "Database restored."
        else
            err "No DB backup found — database NOT restored!"
        fi
    fi

    if [[ $_PKGS_UPDATED -eq 1 ]]; then
        warn "Restoring packages..."
        if [[ -f "$BACKUP_DIR/requirements.lock.bak" ]]; then
            "$PIP" install -q --force-reinstall -r "$BACKUP_DIR/requirements.lock.bak" >> "$LOG" 2>&1
            if [[ $? -eq 0 ]]; then
                ok "Packages restored."
            else
                err "Failed to restore packages — please check manually!"
                err "Backup: $BACKUP_DIR/requirements.lock.bak"
            fi
        else
            err "No package backup found — packages NOT restored!"
        fi
    fi

    warn "Restarting service..."
    systemctl --user restart "$SERVICE" >> "$LOG" 2>&1 || true
    sleep 2
    if systemctl --user is-active --quiet "$SERVICE"; then
        ok "Service is running again."
    else
        err "Service failed to start!"
        err "Check manually: journalctl --user -u $SERVICE -n 50"
    fi

    echo "" | tee -a "$LOG"
    err "Update failed. Log: $LOG"
    exit 1
}

# ── Git pull ───────────────────────────────────────────────────
git_pull() {
    step "── Pulling latest code ─────────────────────────────────"

    if ! git -C "$SCRIPT_DIR" rev-parse --is-inside-work-tree &>/dev/null; then
        warn "Not a git repository — skipping git pull."
        return
    fi

    info "Fetching updates..."
    if ! git -C "$SCRIPT_DIR" pull --ff-only >> "$LOG" 2>&1; then
        err "git pull failed. Resolve conflicts manually and try again."
        exit 1
    fi
    ok "Code up to date."
}

# ── Preflight ──────────────────────────────────────────────────
preflight() {
    step "── Preflight check ─────────────────────────────────────"

    [[ -d "$VENV" ]] || { err "venv not found. Please run install.sh first."; exit 1; }
    [[ -f "$SCRIPT_DIR/requirements.txt" ]] || { err "requirements.txt not found."; exit 1; }
    [[ -f "$DB" ]] || { err "Database not found: $DB"; exit 1; }

    ok "venv found"
    ok "requirements.txt found"
    ok "Database found"

    local free_mb
    free_mb=$(df -m "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
    if [[ $free_mb -lt 200 ]]; then
        err "Not enough disk space: ${free_mb} MB (need at least 200 MB)"
        exit 1
    fi
    ok "Free disk space: ${free_mb} MB"
}

# ── Backup ─────────────────────────────────────────────────────
backup() {
    step "── Creating backup ─────────────────────────────────────"

    info "Freezing current package versions..."
    "$PIP" freeze > "$BACKUP_DIR/requirements.lock.bak"
    ok "Package backup: $BACKUP_DIR/requirements.lock.bak"

    info "Backing up database..."
    cp "$DB" "$BACKUP_DIR/db.sqlite3.bak"
    ok "DB backup: $BACKUP_DIR/db.sqlite3.bak ($(du -h "$BACKUP_DIR/db.sqlite3.bak" | cut -f1))"
}

# ── Show available updates ─────────────────────────────────────
show_outdated() {
    step "── Available updates ───────────────────────────────────"

    local outdated
    outdated=$("$PIP" list --outdated --format=columns 2>/dev/null | tail -n +3 || true)

    if [[ -z "$outdated" ]]; then
        ok "All packages are up to date."
        echo ""
        echo -e "${GREEN}Nothing to do.${NC}"
        exit 0
    fi

    echo ""
    echo -e "${CYAN}  Package                   Current       Available${NC}"
    echo -e "  ──────────────────────────────────────────────────"
    echo "$outdated" | while IFS= read -r line; do
        echo "  $line" | tee -a "$LOG"
    done
    echo ""
}

# ── Compatibility check (dry-run) ──────────────────────────────
dryrun() {
    step "── Compatibility check (dry-run) ───────────────────────"

    info "Simulating update..."
    local dry_output
    if ! dry_output=$("$PIP" install --dry-run -r "$SCRIPT_DIR/requirements.txt" 2>&1); then
        err "Dry-run failed:"
        echo "$dry_output" | tee -a "$LOG"
        err "Update aborted — no changes made."
        exit 1
    fi

    if echo "$dry_output" | grep -qi "conflict\|incompatible\|error"; then
        err "Conflicts detected:"
        echo "$dry_output" | grep -i "conflict\|incompatible\|error" | tee -a "$LOG"
        err "Update aborted."
        exit 1
    fi

    ok "Dry-run successful — no conflicts detected."
}

# ── Confirm ────────────────────────────────────────────────────
confirm() {
    echo ""
    read -rp "$(echo -e "${YELLOW}  Proceed with update? [y/N]:${NC} ")" yn
    yn="${yn:-N}"
    if [[ "${yn,,}" != "y" && "${yn,,}" != "j" ]]; then
        warn "Update cancelled."
        exit 0
    fi
}

# ── Update packages ────────────────────────────────────────────
update_packages() {
    step "── Updating packages ───────────────────────────────────"

    info "Installing updates..."
    REQ_FILE="$SCRIPT_DIR/requirements.lock.txt"
    [[ -f "$REQ_FILE" ]] || REQ_FILE="$SCRIPT_DIR/requirements.txt"
    if ! "$PIP" install -q -r "$REQ_FILE" >> "$LOG" 2>&1; then
        err "pip install failed."
        rollback "pip install failed"
    fi
    _PKGS_UPDATED=1

    info "Checking dependencies (pip check)..."
    if ! "$PIP" check >> "$LOG" 2>&1; then
        err "pip check: dependency conflicts after update!"
        rollback "pip check failed"
    fi
    ok "Packages updated and dependencies consistent."
}

# ── Django system check ────────────────────────────────────────
django_check() {
    step "── Django system check ─────────────────────────────────"

    if ! $MANAGE check --deploy >> "$LOG" 2>&1; then
        err "manage.py check failed."
        rollback "Django check failed"
    fi
    ok "Django check passed."
}

# ── Migrations ─────────────────────────────────────────────────
migrate() {
    step "── Migrating database ──────────────────────────────────"

    if $MANAGE migrate --check >> "$LOG" 2>&1; then
        ok "No pending migrations."
        return
    fi

    info "Running migrations..."
    if ! $MANAGE migrate --run-syncdb -v 0 >> "$LOG" 2>&1; then
        err "Migration failed."
        rollback "migrate failed"
    fi
    _DB_MIGRATED=1
    ok "Migrations successful."
}

# ── Static files ───────────────────────────────────────────────
collectstatic() {
    step "── Collecting static files ─────────────────────────────"

    if ! $MANAGE collectstatic --noinput -v 0 >> "$LOG" 2>&1; then
        err "collectstatic failed."
        rollback "collectstatic failed"
    fi
    ok "Static files updated."
}

# ── Restart service ────────────────────────────────────────────
restart_service() {
    step "── Restarting service ──────────────────────────────────"

    info "Restarting $SERVICE..."
    systemctl --user restart "$SERVICE"
    sleep 2

    if systemctl --user is-active --quiet "$SERVICE"; then
        ok "Service is running."
    else
        err "Service failed to start!"
        rollback "Service start failed"
    fi
}

# ── Summary ────────────────────────────────────────────────────
summary() {
    echo ""
    echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║           Update successful! ✓               ║${NC}"
    echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Log:       ${CYAN}$LOG${NC}"
    echo -e "  DB backup: ${CYAN}$BACKUP_DIR/db.sqlite3.bak${NC}"
    echo ""
}

# ── Main ───────────────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"
echo "=== Update $(date) ===" >> "$LOG"

echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║    Podman Kube Generator — Update Script     ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════╝${NC}"

preflight
git_pull
backup
show_outdated
dryrun
confirm
update_packages
django_check
migrate
collectstatic
restart_service
summary

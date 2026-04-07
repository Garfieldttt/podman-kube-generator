#!/bin/bash
# =============================================================================
# Podman Kube Generator — Update Script
# Prüft Kompatibilität, updated Pakete + DB, rollback bei Fehler
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

# Was wurde bereits geändert (für Rollback)
_PKGS_UPDATED=0
_DB_MIGRATED=0

# ── Farben ─────────────────────────────────────────────────────
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

    # Kein set -e im Rollback — jeder Schritt wird versucht
    set +e

    if [[ $_DB_MIGRATED -eq 1 ]]; then
        warn "Stelle Datenbank wieder her..."
        if [[ -f "$BACKUP_DIR/db.sqlite3.bak" ]]; then
            cp "$BACKUP_DIR/db.sqlite3.bak" "$DB"
            ok "Datenbank wiederhergestellt."
        else
            err "Kein DB-Backup gefunden — Datenbank NICHT wiederhergestellt!"
        fi
    fi

    if [[ $_PKGS_UPDATED -eq 1 ]]; then
        warn "Stelle Pakete wieder her..."
        if [[ -f "$BACKUP_DIR/requirements.lock.bak" ]]; then
            "$PIP" install -q --force-reinstall -r "$BACKUP_DIR/requirements.lock.bak" >> "$LOG" 2>&1
            if [[ $? -eq 0 ]]; then
                ok "Pakete wiederhergestellt."
            else
                err "Fehler beim Wiederherstellen der Pakete — bitte manuell prüfen!"
                err "Backup: $BACKUP_DIR/requirements.lock.bak"
            fi
        else
            err "Kein Paket-Backup gefunden — Pakete NICHT wiederhergestellt!"
        fi
    fi

    warn "Starte Service neu..."
    systemctl --user restart "$SERVICE" >> "$LOG" 2>&1 || true
    sleep 2
    if systemctl --user is-active --quiet "$SERVICE"; then
        ok "Service läuft wieder."
    else
        err "Service konnte nicht gestartet werden!"
        err "Bitte manuell prüfen: journalctl --user -u $SERVICE -n 50"
    fi

    echo "" | tee -a "$LOG"
    err "Update fehlgeschlagen. Log: $LOG"
    exit 1
}

# ── Voraussetzungen ────────────────────────────────────────────
preflight() {
    step "── Voraussetzungen prüfen ──────────────────────────────"

    [[ -d "$VENV" ]] || { err "venv nicht gefunden. Bitte erst install.sh ausführen."; exit 1; }
    [[ -f "$SCRIPT_DIR/requirements.txt" ]] || { err "requirements.txt nicht gefunden."; exit 1; }
    [[ -f "$DB" ]] || { err "Datenbank nicht gefunden: $DB"; exit 1; }

    ok "venv vorhanden"
    ok "requirements.txt vorhanden"
    ok "Datenbank vorhanden"

    # Freier Speicher (mind. 200 MB)
    local free_mb
    free_mb=$(df -m "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
    if [[ $free_mb -lt 200 ]]; then
        err "Zu wenig freier Speicher: ${free_mb} MB (mind. 200 MB benötigt)"
        exit 1
    fi
    ok "Freier Speicher: ${free_mb} MB"
}

# ── Backup ─────────────────────────────────────────────────────
backup() {
    step "── Backup erstellen ────────────────────────────────────"

    info "Friere aktuelle Paketversionen ein..."
    "$PIP" freeze > "$BACKUP_DIR/requirements.lock.bak"
    ok "Paket-Backup: $BACKUP_DIR/requirements.lock.bak"

    info "Sichere Datenbank..."
    cp "$DB" "$BACKUP_DIR/db.sqlite3.bak"
    ok "DB-Backup: $BACKUP_DIR/db.sqlite3.bak ($(du -h "$BACKUP_DIR/db.sqlite3.bak" | cut -f1))"
}

# ── Verfügbare Updates anzeigen ────────────────────────────────
show_outdated() {
    step "── Verfügbare Updates ──────────────────────────────────"

    local outdated
    outdated=$("$PIP" list --outdated --format=columns 2>/dev/null | tail -n +3 || true)

    if [[ -z "$outdated" ]]; then
        ok "Alle Pakete sind aktuell."
        echo ""
        echo -e "${GREEN}Nichts zu tun.${NC}"
        exit 0
    fi

    echo ""
    echo -e "${CYAN}  Paket                    Aktuell       Verfügbar${NC}"
    echo -e "  ──────────────────────────────────────────────────"
    echo "$outdated" | while IFS= read -r line; do
        echo "  $line" | tee -a "$LOG"
    done
    echo ""
}

# ── Kompatibilitätsprüfung (dry-run) ──────────────────────────
dryrun() {
    step "── Kompatibilität prüfen (dry-run) ─────────────────────"

    info "Simuliere Update..."
    local dry_output
    if ! dry_output=$("$PIP" install --dry-run -r "$SCRIPT_DIR/requirements.txt" 2>&1); then
        err "Dry-run fehlgeschlagen:"
        echo "$dry_output" | tee -a "$LOG"
        err "Update wird abgebrochen — keine Änderungen vorgenommen."
        exit 1
    fi

    # Auf Konflikte prüfen
    if echo "$dry_output" | grep -qi "conflict\|incompatible\|error"; then
        err "Konflikte erkannt:"
        echo "$dry_output" | grep -i "conflict\|incompatible\|error" | tee -a "$LOG"
        err "Update wird abgebrochen."
        exit 1
    fi

    ok "Dry-run erfolgreich — keine Konflikte erkannt."
}

# ── Bestätigung ────────────────────────────────────────────────
confirm() {
    echo ""
    read -rp "$(echo -e "${YELLOW}  Update jetzt durchführen? [j/N]:${NC} ")" yn
    yn="${yn:-N}"
    if [[ "${yn,,}" != "j" && "${yn,,}" != "y" ]]; then
        warn "Update abgebrochen."
        exit 0
    fi
}

# ── Pakete updaten ─────────────────────────────────────────────
update_packages() {
    step "── Pakete aktualisieren ────────────────────────────────"

    info "Installiere Updates..."
    if ! "$PIP" install -q -r "$SCRIPT_DIR/requirements.txt" >> "$LOG" 2>&1; then
        err "pip install fehlgeschlagen."
        rollback "pip install fehlgeschlagen"
    fi
    _PKGS_UPDATED=1

    info "Prüfe Abhängigkeiten (pip check)..."
    if ! "$PIP" check >> "$LOG" 2>&1; then
        err "pip check: Abhängigkeitskonflikte nach Update!"
        rollback "pip check fehlgeschlagen"
    fi
    ok "Pakete aktualisiert und Abhängigkeiten konsistent."
}

# ── Django-Systemcheck ─────────────────────────────────────────
django_check() {
    step "── Django Systemcheck ──────────────────────────────────"

    if ! $MANAGE check --deploy >> "$LOG" 2>&1; then
        err "manage.py check fehlgeschlagen."
        rollback "Django check fehlgeschlagen"
    fi
    ok "Django check erfolgreich."
}

# ── Migrationen ────────────────────────────────────────────────
migrate() {
    step "── Datenbank migrieren ─────────────────────────────────"

    # Erst prüfen ob überhaupt Migrationen ausstehen
    if $MANAGE migrate --check >> "$LOG" 2>&1; then
        ok "Keine ausstehenden Migrationen."
        return
    fi

    info "Führe Migrationen durch..."
    if ! $MANAGE migrate --run-syncdb -v 0 >> "$LOG" 2>&1; then
        err "Migrationen fehlgeschlagen."
        rollback "migrate fehlgeschlagen"
    fi
    _DB_MIGRATED=1
    ok "Migrationen erfolgreich."
}

# ── Statische Dateien ──────────────────────────────────────────
collectstatic() {
    step "── Statische Dateien sammeln ───────────────────────────"

    if ! $MANAGE collectstatic --noinput -v 0 >> "$LOG" 2>&1; then
        err "collectstatic fehlgeschlagen."
        rollback "collectstatic fehlgeschlagen"
    fi
    ok "Statische Dateien aktualisiert."
}

# ── Service neustarten ─────────────────────────────────────────
restart_service() {
    step "── Service neustarten ──────────────────────────────────"

    info "Starte $SERVICE neu..."
    systemctl --user restart "$SERVICE"
    sleep 2

    if systemctl --user is-active --quiet "$SERVICE"; then
        ok "Service läuft."
    else
        err "Service hat sich nicht gestartet!"
        rollback "Service-Start fehlgeschlagen"
    fi
}

# ── Zusammenfassung ────────────────────────────────────────────
summary() {
    local new_versions
    new_versions=$("$PIP" freeze 2>/dev/null | head -20 || true)

    echo ""
    echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║           Update erfolgreich! ✓              ║${NC}"
    echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Log:      ${CYAN}$LOG${NC}"
    echo -e "  DB-Backup: ${CYAN}$BACKUP_DIR/db.sqlite3.bak${NC}"
    echo ""
}

# ── Hauptprogramm ──────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"
echo "=== Update $(date) ===" >> "$LOG"

echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║    Podman Kube Generator — Update Script     ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════╝${NC}"

preflight
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

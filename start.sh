#!/bin/bash
set -e
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "==> .env erstellt – bitte SECRET_KEY setzen!"
fi

if [[ ! -d venv ]]; then
    echo "==> Erstelle venv..."
    python3 -m venv venv
fi

echo "==> Abhängigkeiten installieren..."
venv/bin/pip install -q -r requirements.txt

source venv/bin/activate

echo "==> Migrationen..."
python manage.py migrate --run-syncdb

echo "==> Stacks aus stacks.py importieren/aktualisieren..."
python manage.py load_stacks

echo "==> Starte Dev-Server auf http://127.0.0.1:8000"
python manage.py runserver

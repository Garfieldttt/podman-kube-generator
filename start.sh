#!/bin/bash
set -e
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "==> .env created — please set SECRET_KEY!"
fi

if [[ ! -d venv ]]; then
    echo "==> Creating venv..."
    python3 -m venv venv
fi

echo "==> Installing dependencies..."
venv/bin/pip install -q -r requirements.txt

source venv/bin/activate

echo "==> Running migrations..."
python manage.py migrate --run-syncdb

echo "==> Importing stacks..."
python manage.py load_stacks

echo "==> Starting dev server at http://127.0.0.1:8000"
python manage.py runserver

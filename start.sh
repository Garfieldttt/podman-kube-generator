#!/bin/bash
set -e
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
    cp .env.example .env
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    sed -i "s|DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=${SECRET_KEY}|" .env
    echo "==> .env created with generated SECRET_KEY (edit DJANGO_ALLOWED_HOSTS / SITE_URL as needed)"
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

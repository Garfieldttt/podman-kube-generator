#!/bin/bash
SERVICE="podman-kube-gen.service"

if systemctl --user is-active --quiet "$SERVICE" 2>/dev/null; then
    systemctl --user stop "$SERVICE"
    echo "Service $SERVICE stopped."
elif pkill -f "manage.py runserver" 2>/dev/null; then
    echo "Dev server stopped."
else
    echo "Nothing to stop."
fi

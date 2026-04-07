#!/bin/bash
pkill -f "manage.py runserver" && echo "Server stopped." || echo "No running server found."

#!/bin/bash
pkill -f "manage.py runserver" && echo "Server gestoppt." || echo "Kein laufender Server gefunden."

#!/bin/bash
set -e

echo "Starting SignBridge Flask-SocketIO Server..."
echo "PORT: ${PORT:-5001}"

# Use Python directly instead of gunicorn (Flask-SocketIO requirement)
exec python app.py

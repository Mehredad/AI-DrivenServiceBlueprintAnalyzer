#!/usr/bin/env bash
# Blueprint AI — local development helper
# Usage: ./dev.sh [command]
#
# Commands:
#   ./dev.sh          — start API server (default)
#   ./dev.sh migrate  — run database migrations
#   ./dev.sh test     — run test suite
#   ./dev.sh install  — install all dependencies

set -e

# Load .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
  echo "✓ Loaded .env"
fi

COMMAND="${1:-serve}"

case "$COMMAND" in
  install)
    echo "Installing dependencies..."
    pip install -r requirements.txt
    pip install aiosqlite  # for local SQLite testing
    echo "✓ Dependencies installed"
    ;;

  migrate)
    echo "Running database migrations..."
    cd api && alembic upgrade head
    echo "✓ Migrations complete"
    ;;

  test)
    echo "Running test suite..."
    pytest tests/ -v --tb=short
    ;;

  serve)
    echo "Starting Blueprint AI API server..."
    echo "  API:      http://localhost:8000"
    echo "  Docs:     http://localhost:8000/docs"
    echo "  Frontend: open frontend/index.html in your browser"
    echo ""
    cd api && uvicorn app.main:app --reload --port 8000
    ;;

  *)
    echo "Unknown command: $COMMAND"
    echo "Usage: ./dev.sh [install|migrate|test|serve]"
    exit 1
    ;;
esac

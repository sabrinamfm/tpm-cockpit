#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ ! -f ".venv/bin/activate" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installing / updating dependencies..."
pip install -e ".[dev]" -q

echo "Applying database migrations..."
alembic upgrade head

echo ""
echo "Starting TPM Cockpit → http://127.0.0.1:8000"
echo "Press Ctrl+C to stop."
echo ""
uvicorn app.main:app --reload

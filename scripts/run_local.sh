#!/bin/bash
set -euo pipefail

# SodaAgent - Local development runner
# Usage: ./scripts/run_local.sh

echo "=== SodaAgent Local Development ==="

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1)
echo "Python: $PYTHON_VERSION"

# Navigate to backend
cd "$(dirname "$0")/../backend"

# Create venv if not exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt -q

# Check for .env
if [ ! -f "soda_agent/.env" ]; then
    echo ""
    echo "Warning: soda_agent/.env not found"
    echo "Copy from template: cp ../infrastructure/env/.env.example soda_agent/.env"
    echo "Then set your GOOGLE_API_KEY"
    echo ""
fi

echo ""
echo "Choose run mode:"
echo "  1) adk web  - ADK Developer UI (text + audio testing)"
echo "  2) uvicorn  - FastAPI server (WebSocket endpoints)"
echo ""
read -rp "Mode [1]: " mode

case "${mode:-1}" in
    1)
        echo "Starting ADK Developer UI..."
        adk web soda_agent
        ;;
    2)
        echo "Starting FastAPI server on http://localhost:8080..."
        uvicorn main:app --host 0.0.0.0 --port 8080 --reload
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

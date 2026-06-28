#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Copy .env.example and fill in your API keys:"
    echo "   cp .env.example .env"
    echo ""
fi

if [ ! -d "venv" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv venv
fi

echo "→ Activating venv..."
source venv/bin/activate

echo "→ Installing dependencies..."
pip install -q -r requirements.txt

echo "→ Starting GetAJob server..."
echo "   Dashboard: http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""

cd backend
python main.py

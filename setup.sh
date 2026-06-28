#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== GetAJob Setup ==="
echo ""

# Create venv
if [ ! -d "venv" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate

# Install deps
echo "→ Installing Python dependencies..."
pip install -q -r requirements.txt
echo "   ✓ Dependencies installed"

# Copy .env
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "   ✓ Created .env from template"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your API keys before running:"
    echo "   nano .env"
    echo ""
    echo "   You need at least ONE of:"
    echo "   - ADZUNA_APP_ID + ADZUNA_APP_KEY  (free at developer.adzuna.com)"
    echo "   - RAPIDAPI_KEY                     (free at rapidapi.com — search JSearch)"
    echo ""
    echo "   For email alerts, also add:"
    echo "   - SMTP_EMAIL + SMTP_PASSWORD        (Gmail App Password)"
    echo ""
else
    echo "   ✓ .env already exists"
fi

echo "→ Setup complete. Run with:"
echo "   ./run.sh"

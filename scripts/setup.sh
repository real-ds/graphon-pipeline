#!/usr/bin/env bash
set -euo pipefail

echo "Setting up GraphOne pipeline environment..."

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo "Installing Playwright browser (chromium)..."
playwright install chromium

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — fill in your API keys before running."
fi

mkdir -p data/raw data/processed credentials

echo "Done. Activate with: source .venv/bin/activate"
echo "Then run: python -m src.pipeline.main --phase papers"

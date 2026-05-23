#!/usr/bin/env bash
# Build Sparx Solver Pro.app on macOS (run from project root).
set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: This script must be run on macOS." >&2
  exit 1
fi

echo "==> Project: $PROJECT_ROOT"

if [[ ! -d .venv ]]; then
  echo "==> Creating virtual environment..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

echo "==> Downloading and staging EasyOCR models..."
python scripts/download_models.py

echo "==> Building .app (this may take several minutes)..."
pyinstaller packaging/SparxSolverPro.spec --noconfirm --clean

APP_PATH="dist/Sparx Solver Pro.app"
if [[ -d "$APP_PATH" ]]; then
  echo ""
  echo "Build complete: $PROJECT_ROOT/$APP_PATH"
  echo "Drag it to Applications, then open from there."
else
  echo "ERROR: Expected app not found at $APP_PATH" >&2
  exit 1
fi

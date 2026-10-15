#!/usr/bin/env bash
# DocMorph - lancement du serveur local (http://localhost:8000).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${DOCMORPH_VENV:-$HOME/.venvs/docmorph}"
HOST="${DOCMORPH_HOST:-127.0.0.1}"
PORT="${DOCMORPH_PORT:-8000}"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "Environnement introuvable ($VENV_DIR). Lancez d'abord : bash scripts/install_wsl.sh" >&2
    exit 1
fi

# Aucun acces reseau apres installation : les modeles Docling sont lus depuis le cache local.
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

cd "$PROJECT_DIR"
echo "DocMorph : http://localhost:$PORT"
exec "$VENV_DIR/bin/uvicorn" docmorph.api.main:app --host "$HOST" --port "$PORT"

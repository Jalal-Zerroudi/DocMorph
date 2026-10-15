#!/usr/bin/env bash
# DocMorph - installation sous WSL2 Ubuntu.
#
# Usage : bash scripts/install_wsl.sh [--cpu] [--no-structure] [--skip-apt]
#   --cpu           installe PyTorch CPU (pas de GPU NVIDIA)
#   --no-structure  n'installe pas Docling (pas de mode "structure" ni d'OCR vers DOCX)
#   --skip-apt      ne touche pas aux paquets systeme
set -euo pipefail

TORCH_VARIANT="cu126"
WITH_STRUCTURE=1
SKIP_APT=0
for arg in "$@"; do
    case "$arg" in
        --cpu) TORCH_VARIANT="cpu" ;;
        --no-structure) WITH_STRUCTURE=0 ;;
        --skip-apt) SKIP_APT=1 ;;
        *) echo "Option inconnue : $arg" >&2; exit 2 ;;
    esac
done

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${DOCMORPH_VENV:-$HOME/.venvs/docmorph}"
PYTHON_VERSION="${DOCMORPH_PYTHON:-3.12}"
# CUDA wheels weigh several hundred MB each; uv's 30 s default timeout is too short on slow links.
export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-600}"

echo "==> Projet : $PROJECT_DIR"
echo "==> Environnement virtuel : $VENV_DIR (Python $PYTHON_VERSION)"

if [[ "$SKIP_APT" -eq 0 ]]; then
    echo "==> Paquets systeme (sudo)"
    sudo apt-get update
    # Ubuntu >= 24.04 renomme libmagic1 en libmagic1t64.
    if apt-cache show libmagic1t64 >/dev/null 2>&1; then LIBMAGIC=libmagic1t64; else LIBMAGIC=libmagic1; fi
    sudo apt-get install -y --no-install-recommends \
        libreoffice-core libreoffice-writer libreoffice-calc libreoffice-impress \
        tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng tesseract-ocr-ara \
        ghostscript unpaper pngquant qpdf \
        pandoc "$LIBMAGIC" curl ca-certificates \
        fonts-noto-core fonts-noto-mono fonts-dejavu fonts-liberation2 \
        fonts-crosextra-carlito fonts-crosextra-caladea fonts-kacst fonts-arabeyes
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "==> Installation de uv (gestionnaire Python)"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "==> Creation de l'environnement virtuel"
uv python install "$PYTHON_VERSION"
uv venv --python "$PYTHON_VERSION" --allow-existing "$VENV_DIR"
export VIRTUAL_ENV="$VENV_DIR"
export PATH="$VENV_DIR/bin:$PATH"

if [[ "$WITH_STRUCTURE" -eq 1 ]]; then
    echo "==> PyTorch ($TORCH_VARIANT)"
    # CUDA 12.6 : derniere serie de builds PyTorch qui prend encore en charge les GPU Pascal (ex. Quadro P620).
    uv pip install torch torchvision --index-url "https://download.pytorch.org/whl/$TORCH_VARIANT"
    echo "==> DocMorph + Docling"
    uv pip install -e "$PROJECT_DIR[structure,dev]"
    echo "==> Telechargement des modeles Docling (une seule fois)"
    docling-tools models download layout tableformer code_formula picture_classifier
else
    echo "==> DocMorph (sans Docling)"
    uv pip install -e "$PROJECT_DIR[dev]"
fi

echo "==> Verification"
python -m docmorph.doctor

echo
echo "Installation terminee. Lancement : bash scripts/run.sh"

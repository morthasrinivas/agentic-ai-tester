#!/usr/bin/env bash
# =============================================================================
# download_wheels.sh — Pre-download all dependencies as wheel files
#
# Run this ONCE on a machine with internet access.
# The downloaded .whl files are stored in wheels/ and bundled with the project.
# On the remote (offline) machine, setup.sh will install from these files.
#
# Usage:
#   bash download_wheels.sh
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
WHEELS_DIR="$PROJECT_DIR/wheels"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RESET='\033[0m'

if [[ ! -d "$VENV_DIR" ]]; then
    echo "ERROR: .venv not found. Run 'bash setup.sh' first to create the venv." >&2
    exit 1
fi

mkdir -p "$WHEELS_DIR"
source "$VENV_DIR/bin/activate"

echo -e "${CYAN}[wheels]${RESET} Downloading all dependency wheels to wheels/ (CPU-only torch) ..."
# Remove any existing GPU torch/nvidia wheels first
rm -f "$WHEELS_DIR"/torch-[0-9]*.whl
rm -f "$WHEELS_DIR"/nvidia_*.whl
rm -f "$WHEELS_DIR"/triton-*.whl

pip download \
    --dest "$WHEELS_DIR" \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r "$PROJECT_DIR/requirements.txt" \
    --quiet

WHEEL_COUNT=$(find "$WHEELS_DIR" -name "*.whl" | wc -l | tr -d ' ')
echo -e "${GREEN}[wheels]${RESET} Done — $WHEEL_COUNT wheels downloaded to wheels/"
echo ""
echo "You can now zip the entire project and transfer it to a remote machine."
echo "On the remote machine, run:  bash setup.sh"

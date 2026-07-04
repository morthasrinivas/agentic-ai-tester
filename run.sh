#!/usr/bin/env bash
# =============================================================================
# run.sh — Run the Agentic AI Tester pipeline
#
# Usage:
#   bash run.sh                  # Full pipeline (Agent A + B + C loop)
#   bash run.sh --skip-extraction  # Skip Agent A, reuse existing requirements
#
# The script activates .venv automatically and sets PLAYWRIGHT_BROWSERS_PATH
# so browser binaries are loaded from the local browsers/ directory.
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
BROWSERS_DIR="$PROJECT_DIR/browsers"

GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; RESET='\033[0m'

if [[ ! -d "$VENV_DIR" ]]; then
    echo -e "${RED}[run]${RESET} .venv not found. Run 'bash setup.sh' first." >&2
    exit 1
fi

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    echo -e "${RED}[run]${RESET} .env file not found. Run 'bash setup.sh' first." >&2
    exit 1
fi

export PLAYWRIGHT_BROWSERS_PATH="$BROWSERS_DIR"

echo -e "${CYAN}[run]${RESET} Activating virtual environment ..."
source "$VENV_DIR/bin/activate"

echo -e "${CYAN}[run]${RESET} Starting Agentic AI Tester ..."
python "$PROJECT_DIR/orchestrator.py" "$@"

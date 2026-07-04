#!/usr/bin/env bash
# =============================================================================
# setup.sh — One-time setup for Agentic AI Tester
#
# This script:
#   1. Creates a Python virtual environment (.venv)
#   2. Installs all dependencies from the bundled wheels/ folder (OFFLINE)
#      or falls back to PyPI if wheels are missing
#   3. Installs Playwright browser binaries (Chromium only, ~120 MB)
#      into ./browsers/ so the project is self-contained
#
# Usage:
#   bash setup.sh
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
WHEELS_DIR="$PROJECT_DIR/wheels"
BROWSERS_DIR="$PROJECT_DIR/browsers"

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RESET='\033[0m'
log()  { echo -e "${CYAN}[setup]${RESET} $*"; }
ok()   { echo -e "${GREEN}[setup]${RESET} $*"; }
warn() { echo -e "${YELLOW}[setup]${RESET} $*"; }

# ── Python check ──────────────────────────────────────────────────────────────
PYTHON=$(command -v python3.11 || command -v python3.10 || command -v python3 || true)
if [[ -z "$PYTHON" ]]; then
    echo "ERROR: Python 3.10+ is required but not found." >&2
    exit 1
fi
PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
log "Using Python $PY_VER at $PYTHON"

# ── Create venv ───────────────────────────────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
    log "Creating virtual environment at .venv ..."
    "$PYTHON" -m venv "$VENV_DIR"
    ok "Virtual environment created."
else
    log "Virtual environment already exists — skipping creation."
fi

PIP="$VENV_DIR/bin/pip"
PYTHON_VENV="$VENV_DIR/bin/python"

# ── Upgrade pip ───────────────────────────────────────────────────────────────
log "Upgrading pip ..."
"$PIP" install --quiet --upgrade pip

# ── Install dependencies ──────────────────────────────────────────────────────
WHEEL_COUNT=$(find "$WHEELS_DIR" -name "*.whl" 2>/dev/null | wc -l | tr -d ' ')

if [[ "$WHEEL_COUNT" -gt 0 ]]; then
    ok "Found $WHEEL_COUNT bundled wheel(s) — installing OFFLINE from wheels/ ..."
    "$PIP" install --quiet \
        --no-index \
        --find-links="$WHEELS_DIR" \
        -r "$PROJECT_DIR/requirements.txt"
else
    warn "No bundled wheels found — installing from PyPI (internet required) ..."
    # Use CPU-only torch to avoid downloading multi-GB CUDA packages
    "$PIP" install --quiet \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r "$PROJECT_DIR/requirements.txt"
fi

# ── Install Playwright browsers ───────────────────────────────────────────────
export PLAYWRIGHT_BROWSERS_PATH="$BROWSERS_DIR"

if [[ -d "$BROWSERS_DIR/chromium-"* ]] 2>/dev/null; then
    ok "Playwright Chromium already installed at $BROWSERS_DIR — skipping."
else
    log "Installing Playwright Chromium browser (internet required, ~120 MB) ..."
    "$VENV_DIR/bin/playwright" install chromium
    ok "Playwright Chromium installed."
fi

# ── .env file ─────────────────────────────────────────────────────────────────
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    warn "Copied .env.example → .env"
    warn "IMPORTANT: Edit .env and set your OPENAI_API_KEY before running."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
ok "============================================================"
ok "  Setup complete!"
ok "  Next steps:"
ok "  1. Edit .env and set OPENAI_API_KEY"
ok "  2. Run:  bash run.sh"
ok "============================================================"

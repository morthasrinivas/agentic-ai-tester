#!/usr/bin/env bash
# =============================================================================
# run_tests.sh — Execute the generated Playwright tests with pytest
#
# Usage:
#   bash run_tests.sh                   # Run all generated tests
#   bash run_tests.sh -k "test_login"   # Run tests matching a keyword
#   bash run_tests.sh --headed          # Run with visible browser
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
BROWSERS_DIR="$PROJECT_DIR/browsers"
TESTS_DIR="$PROJECT_DIR/tests"

if [[ ! -d "$VENV_DIR" ]]; then
    echo "ERROR: .venv not found. Run 'bash setup.sh' first." >&2
    exit 1
fi

export PLAYWRIGHT_BROWSERS_PATH="$BROWSERS_DIR"
source "$VENV_DIR/bin/activate"

echo "Running generated Playwright tests ..."
python -m pytest "$TESTS_DIR/generated/" \
    --browser chromium \
    --base-url "https://the-internet.herokuapp.com" \
    -v \
    --tb=short \
    "$@"

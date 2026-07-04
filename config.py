"""
Central configuration for the Agentic AI Tester.
All settings are loaded from environment variables (see .env file).
"""

# SQLite version fix: RHEL/CentOS ships sqlite3 < 3.35.0 which ChromaDB rejects.
# pysqlite3-binary bundles a modern sqlite3 and we swap it in before any chromadb import.
try:
    import sys
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass  # Not installed — system sqlite3 will be used (may fail on old systems)

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Project Paths ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR.parent / "docs"
SRS_DOCX = DOCS_DIR / "Capstone requirements document (2).docx"
SRS_PDF  = DOCS_DIR / "updated_Agentic AI Tester Capstone.pdf"

OUTPUT_DIR       = BASE_DIR / "tests" / "generated"
REPORTS_DIR      = BASE_DIR / "reports"
CHROMA_DIR       = BASE_DIR / "chroma_db"
REQUIREMENTS_JSON = BASE_DIR / "requirements_extracted.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# ── LLM Configuration ────────────────────────────────────────────────────────
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL       = os.getenv("LLM_MODEL", "gpt-4o-mini")        # cheaper default
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

# Embedding model: "openai" uses text-embedding-3-small (needs API key)
#                  "local"  uses sentence-transformers (no API key needed)
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local")
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
LOCAL_EMBEDDING_MODEL  = "all-MiniLM-L6-v2"

# ── Target Site ───────────────────────────────────────────────────────────────
TARGET_BASE_URL = "https://the-internet.herokuapp.com"

# ── Orchestrator ─────────────────────────────────────────────────────────────
MAX_ITERATIONS  = int(os.getenv("MAX_ITERATIONS", "5"))

# ── ChromaDB ─────────────────────────────────────────────────────────────────
CHROMA_COLLECTION = "srs_requirements"
CHUNK_SIZE        = 800
CHUNK_OVERLAP     = 100

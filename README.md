# Agentic AI Tester — Capstone Project

A **multi-agent AI system** that automatically generates and validates Playwright UI tests
from an SRS document using RAG (Retrieval-Augmented Generation).

---

## Architecture

```
SRS Document (docx/pdf)
      │
      ▼
┌─────────────────┐
│    Agent A      │  RAG-based requirement extraction
│  (Extractor)    │  → requirements_extracted.json
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Agent B      │  Playwright test code generation
│  (Generator)    │  → tests/generated/*.py
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Agent C      │  Validation: hallucinations, coverage,
│  (Validator)    │  edge cases, code quality → reports/
└────────┬────────┘
         │
    Issues found?
    ├── YES (iteration < 5) → back to Agent B with fix instructions
    └── NO  (or iter = 5)   → Final Tests + Final Report
```

---

## Quick Start

### Prerequisites
- Python 3.10+ installed
- OpenAI API key

### 1. Setup (first time only)

```bash
cd agentic_ai_tester
bash setup.sh
```

### 2. Configure your API key

```bash
# Edit .env (created automatically by setup.sh)
nano .env
# Set: OPENAI_API_KEY=sk-...
```

### 3. Run the pipeline

```bash
bash run.sh
```

### 4. Run the generated tests

```bash
bash run_tests.sh
# Or with visible browser:
bash run_tests.sh --headed
```

---

## Portable / Offline Usage

To transfer this project to a machine **without internet access**:

**On the source machine (internet required):**
```bash
bash setup.sh               # Install everything + download chromium
bash download_wheels.sh     # Download all .whl files into wheels/
zip -r agentic_ai_tester.zip agentic_ai_tester/
```

**On the remote machine:**
```bash
unzip agentic_ai_tester.zip
cd agentic_ai_tester
bash setup.sh               # Installs from wheels/ (no internet needed)
# Edit .env with your API key, then:
bash run.sh
```

> **Note**: `playwright install chromium` still requires internet (or you can copy
> the `browsers/` directory from the source machine as part of your zip).

---

## Project Structure

```
agentic_ai_tester/
├── agents/
│   ├── agent_a.py          # RAG requirement extractor
│   ├── agent_b.py          # Playwright code generator
│   └── agent_c.py          # Test validator / critic
├── core/
│   ├── models.py            # Pydantic data models
│   ├── doc_loader.py        # PDF / DOCX loader + chunker
│   └── embeddings.py        # ChromaDB + embedding factory
├── tests/
│   ├── conftest.py          # pytest-playwright fixtures
│   └── generated/           # ← Agent B writes test files here
├── reports/                 # ← Agent C writes JSON reports here
├── chroma_db/               # ← Vector store (auto-created)
├── wheels/                  # ← Bundled .whl files (offline install)
├── browsers/                # ← Playwright browser binaries
├── requirements_extracted.json  # ← Agent A output
├── orchestrator.py          # Main entry point
├── config.py                # All configuration
├── .env                     # Your API keys (never commit this)
├── .env.example             # Template
├── setup.sh                 # One-time environment setup
├── run.sh                   # Run the pipeline
├── run_tests.sh             # Run generated Playwright tests
└── download_wheels.sh       # Download wheels for offline use
```

---

## Configuration

Edit `.env` to customise:

| Variable             | Default           | Description                          |
|----------------------|-------------------|--------------------------------------|
| `OPENAI_API_KEY`     | (required)        | Your OpenAI API key                  |
| `LLM_MODEL`          | `gpt-4o-mini`     | LLM model (`gpt-4o`, `gpt-4o-mini`)  |
| `LLM_TEMPERATURE`    | `0.1`             | Lower = more deterministic           |
| `EMBEDDING_PROVIDER` | `local`           | `local` (no key) or `openai`         |
| `MAX_ITERATIONS`     | `5`               | Max Agent B → C loop iterations      |

---

## Agents

### Agent A — Requirement Extractor
- Loads the SRS DOCX (`docs/Capstone requirements document (2).docx`)
- Chunks and embeds the text into ChromaDB using `sentence-transformers/all-MiniLM-L6-v2`
- Queries each feature group's requirements and extracts structured `TestRequirement` objects
- Output: `requirements_extracted.json`

### Agent B — Playwright Generator
- Reads `requirements_extracted.json`
- Groups requirements by feature module
- Generates one `test_<feature>.py` file per feature using GPT
- On re-runs, receives fix instructions from Agent C

### Agent C — Validator / Critic
Checks the generated code for:
1. **Hallucinations** — tests not backed by any requirement
2. **Missing coverage** — requirements with no test
3. **Edge case gaps** — negative/edge scenarios from SRS Section 5 not covered
4. **Code quality** — `time.sleep()`, hardcoded URLs, bare `assert` statements

Produces `reports/iteration_N.json` and `reports/final_report.json`.

---

## Target Application

All tests run against **https://the-internet.herokuapp.com/** — a public QA training site
with 37+ UI demonstration pages (login, checkboxes, alerts, drag-drop, tables, etc.).

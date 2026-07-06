"""
Agent A — Requirement Extractor

Two modes:
  1. Direct (default): Parses the SRS document structure directly using
     core.srs_parser — instant, no LLM required, deterministic output.
  2. LLM mode (--llm-extraction): Uses ChromaDB + LLM to extract requirements.
     More flexible but much slower with local models.
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import List

from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from core.doc_loader import load_document, chunk_text
from core.embeddings import get_or_create_collection, ingest_chunks, query_collection
from core.models import TestRequirement, RequirementsBundle
from core.llm_factory import build_llm, llm_provider_name
from core.json_utils import extract_json
from core.srs_parser import parse_requirements


# ── Known requirement IDs from the SRS ───────────────────────────────────────
REQUIREMENT_GROUPS = [
    ("FR-G",    "Global / Cross-Page",          "/"),
    ("FR-CB",   "Checkboxes",                   "/checkboxes"),
    ("FR-FA",   "Form Authentication / Login",  "/login"),
    ("FR-DD",   "Dropdown",                     "/dropdown"),
    ("FR-DC",   "Dynamic Controls",             "/dynamic_controls"),
    ("FR-DL",   "Dynamic Loading",              "/dynamic_loading"),
    ("FR-UP",   "File Upload",                  "/upload"),
    ("FR-JA",   "JavaScript Alerts",            "/javascript_alerts"),
    ("FR-DDP",  "Drag and Drop",                "/drag_and_drop"),
    ("FR-TB",   "Sortable Data Tables",         "/tables"),
    ("FR-NM",   "Notification Messages",        "/notification_message_rendered"),
    ("FR-EA",   "Entry Ad",                     "/entry_ad"),
    ("FR-TY",   "Typos",                        "/typos"),
    ("FR-ARE",  "Add/Remove Elements",          "/add_remove_elements/"),
    ("FR-DE",   "Disappearing Elements",        "/disappearing_elements"),
    ("FR-HV",   "Hovers",                       "/hovers"),
    ("FR-AB",   "A/B Test",                     "/abtest"),
    ("FR-DCNT", "Dynamic Content",              "/dynamic_content"),
    ("FR-SC",   "Status Codes",                 "/status_codes"),
    ("FR-IN",   "Inputs",                       "/inputs"),
    ("FR-HS",   "Horizontal Slider",            "/horizontal_slider"),
    ("FR-CM",   "Context Menu",                 "/context_menu"),
    ("FR-CD",   "Challenging DOM",              "/challenging_dom"),
    ("FR-EI",   "Exit Intent",                  "/exit_intent"),
    ("FR-JQM",  "JQuery UI Menu",               "/jqueryui/menu"),
    ("FR-JE",   "JavaScript Error",             "/javascript_error"),
    ("FR-LD",   "Large & Deep DOM",             "/large"),
    ("FR-IS",   "Infinite Scroll",              "/infinite_scroll"),
    ("FR-FP",   "Forgot Password",              "/forgot_password"),
    ("FR-GL",   "Geolocation",                  "/geolocation"),
    ("FR-FM",   "Floating Menu",                "/floating_menu"),
    ("FR-SD",   "Shadow DOM",                   "/shadowdom"),
    ("FR-FR",   "Frames",                       "/frames"),
    ("FR-WIN",  "Windows",                      "/windows"),
    ("FR-SHC",  "Shifting Content",             "/shifting_content"),
]

EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a senior QA engineer specialising in test requirement extraction.
Given a section of a Software Requirements Specification (SRS) document,
extract ALL testable requirements for the given feature and return them as a
JSON array.

Rules:
- Each item must conform exactly to this schema:
  {{
    "req_id": "string  (e.g. FR-FA-02)",
    "feature": "string",
    "url_path": "string (relative path like /login)",
    "description": "string",
    "preconditions": ["string"],
    "steps": [{{"action": "string", "expected": "string or null"}}],
    "expected_outcome": "string",
    "is_negative": boolean,
    "is_edge_case": boolean,
    "tags": ["string"]
  }}
- Include both positive AND negative/edge case scenarios.
- For non-deterministic behaviours (typos, dynamic content), mark is_edge_case=true.
- Do NOT invent requirements not present in the context.
- Return ONLY valid JSON — no markdown fences, no explanation.
"""),
    ("human", """Feature group: {feature_name} (IDs starting with {req_prefix})
URL path: {url_path}

Relevant SRS context:
---
{context}
---

Extract all testable requirements for this feature as a JSON array."""),
])


def _build_llm():
    return build_llm(json_mode=True)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _extract_requirements_for_group(
    llm: ChatOpenAI,
    collection,
    req_prefix: str,
    feature_name: str,
    url_path: str,
) -> List[TestRequirement]:
    """Query ChromaDB for context about this feature, then ask LLM to extract requirements."""
    query = f"{req_prefix} {feature_name} {url_path} functional requirements preconditions steps"
    context_chunks = query_collection(collection, query, n_results=6)
    context = "\n\n---\n\n".join(context_chunks)

    chain = EXTRACTION_PROMPT | llm
    response = chain.invoke({
        "feature_name": feature_name,
        "req_prefix": req_prefix,
        "url_path": url_path,
        "context": context,
    })

    raw = response.content.strip()
    parsed = extract_json(raw)
    if not isinstance(parsed, list):
        parsed = [parsed]

    requirements = []
    for item in parsed:
        try:
            requirements.append(TestRequirement(**item))
        except Exception:
            pass
    return requirements


def run(srs_path: Path | None = None, use_llm: bool = False) -> RequirementsBundle:
    """
    Main entry point for Agent A.

    Args:
        srs_path: Override the default SRS document path.
        use_llm:  If True, use LLM-based extraction (slow with local models).
                  If False (default), use the fast direct SRS parser.
    """
    from rich.console import Console
    from rich.progress import track
    console = Console()

    doc_path = srs_path or config.SRS_DOCX

    # ── Always ingest into ChromaDB (for Agent C to use) ────────────────────
    console.print(f"\n[bold cyan]Agent A[/bold cyan] — Loading document: {doc_path.name}")
    text = load_document(doc_path)
    chunks = chunk_text(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    console.print(f"  Loaded {len(text):,} chars → {len(chunks)} chunks")

    collection = get_or_create_collection(
        chroma_dir=config.CHROMA_DIR,
        collection_name=config.CHROMA_COLLECTION,
        embedding_provider=config.EMBEDDING_PROVIDER,
        embedding_model=config.LOCAL_EMBEDDING_MODEL,
    )
    added = ingest_chunks(collection, chunks, doc_id_prefix="srs")
    console.print(f"  ChromaDB: {added} new chunks ingested (collection size: {collection.count()})")

    # ── Extract requirements ──────────────────────────────────────────────────
    if use_llm:
        console.print(f"\n  [LLM mode] LLM provider: [bold]{llm_provider_name()}[/bold]")
        llm = _build_llm()
        all_requirements: List[TestRequirement] = []
        console.print("  Extracting requirements per feature group (LLM)...")
        for req_prefix, feature_name, url_path in track(REQUIREMENT_GROUPS, description="Extracting"):
            try:
                reqs = _extract_requirements_for_group(llm, collection, req_prefix, feature_name, url_path)
                all_requirements.extend(reqs)
            except Exception as exc:
                console.print(f"  [yellow]Warning[/yellow]: {req_prefix} skipped — {exc}")
    else:
        console.print("  [Direct mode] Parsing requirements from SRS structure (no LLM needed)...")
        all_requirements = parse_requirements(doc_path)
        console.print(f"  Parsed {len(all_requirements)} requirements instantly")

    bundle = RequirementsBundle(
        source_document=doc_path.name,
        total_requirements=len(all_requirements),
        requirements=all_requirements,
    )

    with open(config.REQUIREMENTS_JSON, "w", encoding="utf-8") as f:
        json.dump(bundle.model_dump(), f, indent=2)

    console.print(
        f"\n[bold green]Agent A done[/bold green] — "
        f"{len(all_requirements)} requirements extracted → {config.REQUIREMENTS_JSON.name}"
    )
    return bundle

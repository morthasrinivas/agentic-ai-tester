"""
Agent C — Test Validator / Critic

Reviews the generated Playwright test files against the original
requirements and produces a structured ValidationReport flagging:
  1. Hallucinations    — tests for things not in the SRS
  2. Missing coverage  — requirements with no corresponding test
  3. Edge case gaps    — Section 5 edge/negative scenarios not covered
  4. Code quality      — bad patterns (time.sleep, hardcoded URLs, etc.)
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from langchain.prompts import ChatPromptTemplate
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from core.embeddings import get_or_create_collection, query_collection
from core.llm_factory import build_llm, llm_provider_name
from core.json_utils import extract_json
from core.models import (
    RequirementsBundle,
    TestRequirement,
    ValidationIssue,
    ValidationReport,
)


# ── Validation prompt ─────────────────────────────────────────────────────────
VALIDATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a senior QA lead doing a thorough code review of auto-generated Playwright tests.

Your job is to analyse the test file against the requirements and return a JSON object with this schema:
{{
  "issues": [
    {{
      "issue_type": "hallucination | missing_coverage | missing_edge_case | code_quality",
      "severity": "high | medium | low",
      "req_id": "string or null",
      "test_file": "string or null",
      "description": "what is wrong",
      "fix_instruction": "specific instruction to fix it"
    }}
  ],
  "covered_req_ids": ["FR-CB-01", ...],
  "summary": "one-paragraph summary"
}}

Hallucination: test code that tests something NOT in the requirements.
Missing coverage: a requirement ID that has NO test.
Missing edge case: an edge/negative scenario from requirements not tested.
Code quality: time.sleep(), hardcoded https:// URLs, bare assertions without messages, etc.

Be specific — cite req IDs and line content where possible.
Return ONLY valid JSON — no markdown, no explanation.
"""),
    ("human", """Test file: {test_file_name}
--- TEST CODE ---
{test_code}
--- END CODE ---

Requirements this file should cover:
{requirements_json}

Additional SRS context (edge cases, negative scenarios):
{srs_context}

Validate thoroughly and return the JSON report."""),
])


def _build_llm():
    return build_llm(temperature=0.0, json_mode=True)


def _read_test_files(test_files: Dict[str, Path]) -> Dict[str, str]:
    """Read generated test files from disk."""
    result = {}
    for feature, path in test_files.items():
        if path.exists():
            result[feature] = path.read_text(encoding="utf-8")
    return result


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _validate_file(
    llm: ChatOpenAI,
    collection,
    test_file_name: str,
    test_code: str,
    feature_reqs: List[TestRequirement],
) -> dict:
    """Ask the LLM to validate one test file against its requirements."""
    reqs_json = json.dumps([r.model_dump() for r in feature_reqs], indent=2)

    # Pull edge-case context from ChromaDB for this feature
    feature = feature_reqs[0].feature if feature_reqs else test_file_name
    edge_query = f"edge case negative scenario {feature} {feature_reqs[0].url_path if feature_reqs else ''}"
    srs_ctx = "\n\n".join(query_collection(collection, edge_query, n_results=4))

    chain = VALIDATE_PROMPT | llm
    response = chain.invoke({
        "test_file_name": test_file_name,
        "test_code": test_code[:6000],  # guard against token overflow
        "requirements_json": reqs_json,
        "srs_context": srs_ctx,
    })

    raw = response.content.strip()
    return extract_json(raw)


def _static_code_checks(test_code: str, test_file_name: str) -> List[ValidationIssue]:
    """Fast regex-based code quality checks (no LLM needed)."""
    issues = []

    if "time.sleep(" in test_code:
        issues.append(ValidationIssue(
            issue_type="code_quality", severity="high",
            test_file=test_file_name,
            description="time.sleep() detected — blocks test runner and is unreliable",
            fix_instruction="Replace time.sleep() with page.wait_for_selector(), "
                            "expect(locator).to_be_visible(), or page.wait_for_load_state()",
        ))

    hardcoded = re.findall(r'"https?://[^"]*herokuapp[^"]*"', test_code)
    if hardcoded:
        issues.append(ValidationIssue(
            issue_type="code_quality", severity="medium",
            test_file=test_file_name,
            description=f"Hardcoded URL(s) found: {hardcoded[:3]}",
            fix_instruction="Use the base_url pytest fixture instead of hardcoded URLs. "
                            "e.g. page.goto(f'{base_url}/login')",
        ))

    if "assert " in test_code and "assert_that" not in test_code:
        bare = re.findall(r"\n\s+assert [^\n]+", test_code)
        if bare:
            issues.append(ValidationIssue(
                issue_type="code_quality", severity="low",
                test_file=test_file_name,
                description="bare assert statements found instead of Playwright expect()",
                fix_instruction="Replace bare assert with expect(locator).to_be_visible() "
                                "or expect(locator).to_have_text()",
            ))

    return issues


def run(
    test_files: Dict[str, Path],
    bundle: Optional[RequirementsBundle] = None,
    iteration: int = 1,
) -> ValidationReport:
    """
    Main entry point for Agent C.

    Validates all generated test files and returns a ValidationReport.
    Also saves the report to reports/iteration_N.json.
    """
    from rich.console import Console
    from rich.progress import track
    console = Console()

    # Load requirements bundle if not provided
    if bundle is None:
        with open(config.REQUIREMENTS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        bundle = RequirementsBundle(**data)

    console.print(
        f"\n[bold cyan]Agent C[/bold cyan] — Validating iteration {iteration} "
        f"({len(test_files)} test files)"
    )

    collection = get_or_create_collection(
        chroma_dir=config.CHROMA_DIR,
        collection_name=config.CHROMA_COLLECTION,
        embedding_provider=config.EMBEDDING_PROVIDER,
        embedding_model=config.LOCAL_EMBEDDING_MODEL,
    )

    llm = _build_llm()
    console.print(f"  LLM provider: [bold]{llm_provider_name()}[/bold]")
    # If test_files is empty but generated dir has files, pick them up
    if not test_files:
        for f in config.OUTPUT_DIR.glob("test_*.py"):
            feature = f.stem.replace("test_", "").replace("_", " ").title()
            test_files[feature] = f
        if test_files:
            console.print(f"  [dim]Auto-discovered {len(test_files)} test files from output directory[/dim]")

    test_code_map = _read_test_files(test_files)

    # Build per-feature requirement lookup
    feature_req_map: Dict[str, List[TestRequirement]] = {}
    for req in bundle.requirements:
        feature_req_map.setdefault(req.feature, []).append(req)

    all_issues: List[ValidationIssue] = []
    covered_req_ids: set = set()

    for feature_name, code in track(test_code_map.items(), description="Validating"):
        file_name = test_files[feature_name].name
        feature_reqs = feature_req_map.get(feature_name, [])

        # Static checks (fast, no LLM)
        static_issues = _static_code_checks(code, file_name)
        all_issues.extend(static_issues)

        # LLM-powered deep validation
        try:
            result = _validate_file(llm, collection, file_name, code, feature_reqs)
            for item in result.get("issues", []):
                try:
                    all_issues.append(ValidationIssue(**item))
                except Exception:
                    pass
            covered_req_ids.update(result.get("covered_req_ids", []))
        except Exception as exc:
            console.print(f"  [yellow]Warning[/yellow]: LLM validation failed for {file_name} — {exc}")

    # Check for completely missing requirement coverage
    all_req_ids = {r.req_id for r in bundle.requirements}
    uncovered = all_req_ids - covered_req_ids
    for req_id in sorted(uncovered):
        req = next((r for r in bundle.requirements if r.req_id == req_id), None)
        all_issues.append(ValidationIssue(
            issue_type="missing_coverage",
            severity="high",
            req_id=req_id,
            description=f"No test found for requirement {req_id}: "
                        f"{req.description if req else 'unknown'}",
            fix_instruction=f"Add a test case covering {req_id}. "
                            f"Steps: {req.steps if req else 'see SRS'}",
        ))

    coverage_pct = (len(covered_req_ids) / len(all_req_ids) * 100) if all_req_ids else 0.0
    high_medium = [i for i in all_issues if i.severity in ("high", "medium")]
    passed = len(high_medium) == 0

    report = ValidationReport(
        iteration=iteration,
        passed=passed,
        total_issues=len(all_issues),
        issues=all_issues,
        coverage_percentage=round(coverage_pct, 1),
        summary=(
            f"Iteration {iteration}: {len(all_issues)} issues found "
            f"({len(high_medium)} high/medium). "
            f"Coverage: {coverage_pct:.1f}%. "
            f"{'PASSED ✓' if passed else 'NEEDS FIXES ✗'}"
        ),
    )

    report_path = config.REPORTS_DIR / f"iteration_{iteration}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2)

    severity_color = "green" if passed else "red"
    console.print(
        f"[bold {severity_color}]Agent C done[/bold {severity_color}] — "
        f"{report.summary}"
    )
    return report

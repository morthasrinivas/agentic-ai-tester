"""
Agent B — Playwright Test Code Generator

Takes the structured requirements from Agent A (or fix instructions from Agent C)
and generates pytest-playwright Python test files grouped by feature.
"""

from __future__ import annotations
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from langchain.prompts import ChatPromptTemplate
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from core.models import RequirementsBundle, TestRequirement, ValidationReport
from core.llm_factory import build_llm, llm_provider_name
from core.json_utils import extract_json


# ── Code generation prompt ────────────────────────────────────────────────────
GENERATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a senior test automation engineer specialising in Playwright (Python).
Write pytest-playwright test code that is:
- Clean, readable, and follows pytest best practices
- Uses page fixtures from pytest-playwright (never manual browser/context creation)
- Uses specific, robust locators (prefer role-based and text-based, avoid fragile CSS/XPath)
- Has proper assertions with helpful failure messages
- Handles async behaviours with expect() + timeouts, never time.sleep()
- Groups related tests in a class named Test<FeatureName>
- Has a module-level docstring describing what is tested
- Includes the base_url fixture pattern for configurable URL

Do NOT:
- Use time.sleep() — use page.wait_for_selector() or expect()
- Hardcode absolute URLs — use the base_url fixture
- Add comments that merely restate the code
- Import unused modules

Return ONLY the Python source code — no markdown fences, no explanation.
"""),
    ("human", """Generate Playwright tests for the feature: {feature_name}
Base URL: {base_url}

Requirements to cover:
{requirements_json}

{fix_context}

Write a complete pytest file with all test cases."""),
])


def _build_llm():
    return build_llm(json_mode=False)  # code generation — not JSON mode


def _sanitize_module_name(feature_name: str) -> str:
    """Convert feature name to a valid Python module filename."""
    name = re.sub(r"[^a-zA-Z0-9]+", "_", feature_name).strip("_").lower()
    return f"test_{name}.py"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _generate_test_file(
    llm: ChatOpenAI,
    feature_name: str,
    requirements: List[TestRequirement],
    fix_context: str = "",
) -> str:
    """Call LLM to generate a Playwright test file for one feature group."""
    reqs_json = json.dumps(
        [r.model_dump() for r in requirements],
        indent=2,
    )
    chain = GENERATE_PROMPT | llm
    response = chain.invoke({
        "feature_name": feature_name,
        "base_url": config.TARGET_BASE_URL,
        "requirements_json": reqs_json,
        "fix_context": f"Fix instructions from review:\n{fix_context}" if fix_context else "",
    })
    code = response.content.strip()
    # Strip markdown fences but keep the code as-is (not JSON)
    code = re.sub(r"^```[a-z]*\s*\n?", "", code, flags=re.MULTILINE)
    code = re.sub(r"\n?```\s*$", "", code, flags=re.MULTILINE)
    return code.strip()


def _group_by_feature(requirements: List[TestRequirement]) -> Dict[str, List[TestRequirement]]:
    """Group requirements by feature name."""
    groups: Dict[str, List[TestRequirement]] = defaultdict(list)
    for req in requirements:
        groups[req.feature].append(req)
    return dict(groups)


def _build_fix_context(report: ValidationReport, feature_name: str) -> str:
    """Extract fix instructions relevant to a specific feature from a validation report."""
    relevant = [
        f"- [{i.issue_type}] {i.description}\n  FIX: {i.fix_instruction}"
        for i in report.issues
        if i.req_id and feature_name.lower() in (i.req_id.lower() + (i.test_file or "").lower())
        or not i.req_id
    ]
    return "\n".join(relevant) if relevant else ""


def run(
    bundle: Optional[RequirementsBundle] = None,
    previous_report: Optional[ValidationReport] = None,
    iteration: int = 1,
) -> Dict[str, Path]:
    """
    Main entry point for Agent B.

    Generates one .py test file per feature group and writes them to tests/generated/.
    Returns a mapping of {feature_name: file_path}.
    """
    from rich.console import Console
    from rich.progress import track
    console = Console()

    # Load requirements from disk if not provided in memory
    if bundle is None:
        if not config.REQUIREMENTS_JSON.exists():
            raise FileNotFoundError(
                f"Requirements file not found: {config.REQUIREMENTS_JSON}\n"
                "Run Agent A first."
            )
        with open(config.REQUIREMENTS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        bundle = RequirementsBundle(**data)

    console.print(
        f"\n[bold cyan]Agent B[/bold cyan] — Generating Playwright tests "
        f"(iteration {iteration}, {bundle.total_requirements} requirements)"
    )

    llm = _build_llm()
    console.print(f"  LLM provider: [bold]{llm_provider_name()}[/bold]")
    feature_groups = _group_by_feature(bundle.requirements)
    generated: Dict[str, Path] = {}

    for feature_name, reqs in track(feature_groups.items(), description="Generating"):
        fix_ctx = ""
        if previous_report:
            fix_ctx = _build_fix_context(previous_report, feature_name)

        try:
            code = _generate_test_file(llm, feature_name, reqs, fix_context=fix_ctx)
        except Exception as exc:
            console.print(f"  [yellow]Warning[/yellow]: {feature_name} generation failed — {exc}")
            # Use existing file if present, otherwise generate a stub
            filename = _sanitize_module_name(feature_name)
            file_path = config.OUTPUT_DIR / filename
            if file_path.exists():
                generated[feature_name] = file_path
                console.print(f"  [dim]Using existing file: {filename}[/dim]")
            else:
                stub = _make_stub(feature_name, reqs)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(stub)
                generated[feature_name] = file_path
            continue

        filename = _sanitize_module_name(feature_name)
        file_path = config.OUTPUT_DIR / filename

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        generated[feature_name] = file_path

    console.print(
        f"[bold green]Agent B done[/bold green] — "
        f"{len(generated)} test files written to {config.OUTPUT_DIR}"
    )
    return generated


def _make_stub(feature_name: str, reqs: List[TestRequirement]) -> str:
    """Generate a minimal stub test file when LLM generation fails."""
    class_name = re.sub(r"[^a-zA-Z0-9]", "", feature_name.title())
    lines = [
        f'"""Tests for {feature_name} — stub (LLM generation failed)"""',
        "import pytest",
        "from playwright.sync_api import Page, expect",
        "",
        f"class Test{class_name}:",
    ]
    for req in reqs[:5]:
        fn = re.sub(r"[^a-z0-9]+", "_", req.description.lower())[:50]
        lines += [
            f"    def test_{fn}(self, page: Page, base_url: str):",
            f'        """[{req.req_id}] {req.description}"""',
            f"        page.goto(f'{{base_url}}{req.url_path}')",
            "        expect(page).not_to_have_title('')",
            "",
        ]
    return "\n".join(lines)

"""
Orchestrator — Main Entrypoint

Drives the full Agentic AI Tester pipeline:
  1. Agent A: Extract requirements from SRS document (once)
  2. Agent B → Agent C loop (max MAX_ITERATIONS attempts)
     - Agent B generates/regenerates Playwright tests
     - Agent C validates and produces a report
     - If passed or max iterations reached → stop
  3. Print final summary
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

import config

console = Console()


def _print_banner():
    from core.llm_factory import llm_provider_name
    console.print(Panel.fit(
        "[bold cyan]Agentic AI Tester[/bold cyan]\n"
        "Multi-Agent Playwright Test Generator\n"
        f"[dim]LLM: {llm_provider_name()}  |  Max iterations: {config.MAX_ITERATIONS}[/dim]",
        border_style="cyan",
    ))


def _print_iteration_summary(iteration: int, report) -> None:
    table = Table(box=box.SIMPLE, title=f"Iteration {iteration} Results")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Status",        "[green]PASSED ✓[/green]" if report.passed else "[red]NEEDS FIXES ✗[/red]")
    table.add_row("Coverage",      f"{report.coverage_percentage}%")
    table.add_row("Total Issues",  str(report.total_issues))
    high_med = [i for i in report.issues if i.severity in ("high", "medium")]
    table.add_row("High/Medium",   str(len(high_med)))
    console.print(table)

    if report.issues:
        console.print("\n[bold]Top Issues:[/bold]")
        for issue in report.issues[:8]:
            color = "red" if issue.severity == "high" else "yellow" if issue.severity == "medium" else "dim"
            console.print(
                f"  [{color}][{issue.severity.upper()}][/{color}] "
                f"[{issue.issue_type}] {issue.description}"
            )
        if len(report.issues) > 8:
            console.print(f"  ... and {len(report.issues) - 8} more (see reports/)")


def _print_final_summary(reports: list, test_files: dict) -> None:
    last = reports[-1]
    console.print(Panel.fit(
        f"[bold]Pipeline Complete[/bold]\n\n"
        f"Iterations run:    {len(reports)}\n"
        f"Final coverage:    {last.coverage_percentage}%\n"
        f"Final issues:      {last.total_issues}\n"
        f"Final status:      {'[green]PASSED[/green]' if last.passed else '[yellow]MAX ATTEMPTS REACHED[/yellow]'}\n\n"
        f"Test files: [dim]{config.OUTPUT_DIR}[/dim]\n"
        f"Reports:    [dim]{config.REPORTS_DIR}[/dim]",
        border_style="green" if last.passed else "yellow",
        title="Final Results",
    ))

    console.print("\n[bold]Generated Test Files:[/bold]")
    for feature, path in test_files.items():
        size = path.stat().st_size if path.exists() else 0
        console.print(f"  {path.name:<55} {size:>6,} bytes")


def main(skip_agent_a: bool = False) -> None:
    """
    Run the full pipeline.

    Args:
        skip_agent_a: If True, skip Agent A and use existing requirements_extracted.json.
                      Useful when re-running after the document has already been processed.
    """
    _print_banner()

    # ── Step 1: Agent A ───────────────────────────────────────────────────────
    from agents import agent_a, agent_b, agent_c
    from core.models import RequirementsBundle

    if skip_agent_a and config.REQUIREMENTS_JSON.exists():
        console.print("\n[dim]Skipping Agent A — using existing requirements_extracted.json[/dim]")
        with open(config.REQUIREMENTS_JSON, encoding="utf-8") as f:
            bundle = RequirementsBundle(**json.load(f))
    else:
        bundle = agent_a.run()

    # ── Step 2: Agent B → Agent C loop ────────────────────────────────────────
    reports = []
    test_files = {}
    previous_report = None

    for iteration in range(1, config.MAX_ITERATIONS + 1):
        console.print(f"\n{'─' * 60}")
        console.print(f"[bold]Iteration {iteration} / {config.MAX_ITERATIONS}[/bold]")

        # Agent B: generate (or regenerate) tests
        test_files = agent_b.run(
            bundle=bundle,
            previous_report=previous_report,
            iteration=iteration,
        )

        # Agent C: validate
        report = agent_c.run(
            test_files=test_files,
            bundle=bundle,
            iteration=iteration,
        )
        reports.append(report)
        previous_report = report

        _print_iteration_summary(iteration, report)

        if report.passed:
            console.print(f"\n[bold green]✓ All checks passed at iteration {iteration}![/bold green]")
            break

        if iteration == config.MAX_ITERATIONS:
            console.print(
                f"\n[bold yellow]⚠ Max iterations ({config.MAX_ITERATIONS}) reached. "
                "Presenting best available output.[/bold yellow]"
            )

    # ── Step 3: Final summary ─────────────────────────────────────────────────
    _print_final_summary(reports, test_files)

    # Write a consolidated final report
    final_report_path = config.REPORTS_DIR / "final_report.json"
    last_report = reports[-1]
    with open(final_report_path, "w", encoding="utf-8") as f:
        json.dump({
            "iterations_run": len(reports),
            "final_passed": last_report.passed,
            "final_coverage_percentage": last_report.coverage_percentage,
            "final_total_issues": last_report.total_issues,
            "all_iterations": [r.model_dump() for r in reports],
        }, f, indent=2)

    console.print(f"\n[dim]Final report saved to: {final_report_path}[/dim]")

    # Exit with non-zero code if not fully passing (useful for CI)
    if not last_report.passed:
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agentic AI Tester — Playwright Test Generator")
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip Agent A and reuse existing requirements_extracted.json",
    )
    args = parser.parse_args()
    main(skip_agent_a=args.skip_extraction)

"""
Standalone per-feature report runner using Agent C static checks only.
No LLM required — instant results.
"""
import sys, json, re
sys.path.insert(0, ".")

import config
from core.models import RequirementsBundle
from agents.agent_c import _static_code_checks, _read_test_files

# ── Load data ────────────────────────────────────────────────────────────────
with open(config.REQUIREMENTS_JSON) as f:
    bundle = RequirementsBundle(**json.load(f))

test_files = {}
for f in sorted(config.OUTPUT_DIR.glob("test_*.py")):
    feature = f.stem.replace("test_", "").replace("_", " ").title()
    test_files[feature] = f

test_code_map = _read_test_files(test_files)

# ── Per-feature analysis ─────────────────────────────────────────────────────
feature_reqs_map = {}
for r in bundle.requirements:
    feature_reqs_map.setdefault(r.feature, []).append(r.req_id)

all_issues = []
results = {}

for feature_name, code in test_code_map.items():
    fname = test_files[feature_name].name
    issues = _static_code_checks(code, fname)
    test_fns = re.findall(r"def (test_\w+)", code)
    is_stub = "LLM generation failed" in code or "stub" in code.lower()
    has_expect = "expect(" in code
    has_assert = "assert " in code

    results[feature_name] = {
        "file": fname,
        "lines": len(code.splitlines()),
        "test_count": len(test_fns),
        "test_names": test_fns,
        "has_playwright_expect": has_expect,
        "has_assert": has_assert,
        "is_stub": is_stub,
        "issues": issues,
        "requirements": feature_reqs_map.get(feature_name, []),
    }
    all_issues.extend(issues)

# ── Print report ─────────────────────────────────────────────────────────────
print()
print("=" * 120)
print("  AGENTIC AI TESTER — PER-FEATURE RESULTS REPORT")
print(f"  LLM: Ollama (llama3)  |  {len(test_files)} features  |  {bundle.total_requirements} requirements")
print("=" * 120)

H = "{:<35} {:<42} {:>5} {:>5} {:>7} {:>5} {:>6}"
print()
print(H.format("Feature", "Test File", "Lines", "Tests", "Expect?", "Stub?", "Issues"))
print("-" * 110)

for feat, r in sorted(results.items()):
    stub_mark = "YES" if r["is_stub"] else "no"
    exp_mark  = "YES" if r["has_playwright_expect"] else "no"
    print(H.format(
        feat[:35],
        r["file"][:42],
        r["lines"],
        r["test_count"],
        exp_mark,
        stub_mark,
        len(r["issues"]),
    ))

print()
print("=" * 120)
print("  PER-FEATURE DETAIL")
print("=" * 120)

for feat, r in sorted(results.items()):
    req_ids = r["requirements"]
    print()
    print(f"  Feature : {feat}")
    print(f"  File    : {r['file']}  ({r['lines']} lines)")
    print(f"  Req IDs : {', '.join(req_ids) if req_ids else 'none mapped'}")
    print(f"  Tests   : {r['test_count']}  {'(stub — minimal implementation)' if r['is_stub'] else ''}")
    if r["test_names"]:
        for tn in r["test_names"][:6]:
            print(f"            • {tn}")
        if len(r["test_names"]) > 6:
            print(f"            ... {len(r['test_names'])-6} more")
    print(f"  Quality : Playwright expect()={'YES' if r['has_playwright_expect'] else 'NO'}  "
          f"bare assert={'YES' if r['has_assert'] else 'no'}")
    if r["issues"]:
        for issue in r["issues"]:
            print(f"  [{issue.severity.upper()}] {issue.issue_type}: {issue.description[:90]}")
    else:
        print("  No static issues detected")

print()
print("=" * 120)
print("  SUMMARY")
print("=" * 120)
total_tests  = sum(r["test_count"] for r in results.values())
stub_count   = sum(1 for r in results.values() if r["is_stub"])
llm_count    = sum(1 for r in results.values() if not r["is_stub"])
high_issues  = [i for i in all_issues if i.severity == "high"]
med_issues   = [i for i in all_issues if i.severity == "medium"]
low_issues   = [i for i in all_issues if i.severity == "low"]
all_features = set(r.feature for r in bundle.requirements)
covered      = set(results.keys())
uncovered    = all_features - covered

print(f"  Total features        : {len(results)}")
print(f"  LLM-generated files   : {llm_count}  (full Playwright implementation)")
print(f"  Stub files            : {stub_count}  (minimal placeholder)")
print(f"  Total test functions  : {total_tests}")
print(f"  Requirements covered  : {len(covered)}/{len(all_features)} features")
if uncovered:
    print(f"  Uncovered features    : {', '.join(sorted(uncovered))}")
print()
print(f"  Static issue counts:")
print(f"    High   (blocking) : {len(high_issues)}")
print(f"    Medium (warning)  : {len(med_issues)}")
print(f"    Low    (info)     : {len(low_issues)}")
print(f"    Total             : {len(all_issues)}")
print()

if high_issues:
    print("  HIGH severity issues:")
    for i in high_issues:
        print(f"    [{i.test_file}] {i.description}")

print()
print("  NOTE: 'Stub' files contain placeholder tests generated when Ollama LLM call")
print("        timed out. They navigate to the page and verify a basic title assertion.")
print("        Run 'bash run.sh' with OPENAI_API_KEY set to generate full implementations.")
print()

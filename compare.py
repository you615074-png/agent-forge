"""
AgentForge — Multi-Plan Comparison Engine (v0.6)
=================================================
Run a single task through every configured agent, collect the outputs,
score them on quality metrics, and present a ranked comparison.

Usage:
  from compare import compare_plans
  result = compare_plans(task, config, mock=False)
  print(result["summary"])  # formatted comparison table
"""

import os
import re
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

from executor import execute
from console import (
    cprint, styled, header, section, dim, bold, green, red, yellow, cyan, magenta,
    ok, fail, Colors, STAGE_COLORS,
)


# ── Scoring weights ──
SCORE_WEIGHTS = {
    "file_count":    0.15,
    "code_lines":    0.25,
    "has_tests":     0.20,
    "has_docs":      0.15,
    "has_errors":    0.15,
    "structure":     0.10,
}


def compare_plans(
    task: str,
    config: dict,
    mock: bool = False,
    agents_filter: Optional[list[str]] = None,
) -> dict:
    """
    Run `task` through every agent (or filtered subset), collect and rank results.

    Returns:
      {
        "results": [...],       # per-agent result dicts
        "rankings": [...],      # sorted by score (best first)
        "winner": str,          # agent name of the winner
        "session_dir": str,     # where outputs were saved
        "summary": str,         # formatted comparison table for display
      }
    """
    agents = config.get("agents", {})
    if agents_filter:
        agents = {k: v for k, v in agents.items() if k in agents_filter}
    if not agents:
        return {"error": "No agents configured. Check your forge.yaml."}

    # ── Setup session ──
    work_dir_root = os.path.join(
        os.path.dirname(__file__),
        config.get("executor", {}).get("work_dir", "sessions")
    )
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    task_hash = hashlib.md5(task.encode()).hexdigest()[:8]
    session_dir = os.path.join(work_dir_root, f"compare-{ts}-{task_hash}")
    os.makedirs(session_dir, exist_ok=True)

    timeout = config.get("executor", {}).get("timeout_seconds", 120)
    stage_prefix = "coding"

    # ── Header ──
    header(f"Multi-Plan Comparison — {len(agents)} agents", 60)
    cprint(f"  {bold('Task:')} {task[:100]}")
    cprint(f"  {bold('Dir:')}  {dim(session_dir)}\n")

    results: list[dict] = []
    agent_names = list(agents.keys())

    for i, (agent_name, agent_config) in enumerate(agents.items()):
        label = agent_config.get("provider") or agent_config.get("cli", "?")

        cprint(f"  [{i+1}/{len(agents)}] {cyan(agent_name)} {dim(f'({label})')}...", end=" ")

        if mock:
            # Generate mock output for comparison
            mock_output = _generate_mock_output(agent_name)
            mock_files = _create_mock_files(session_dir, agent_name, mock_output)
            result = {
                "success": True,
                "agent": agent_name,
                "stdout": mock_output,
                "produced_files": mock_files,
                "duration_ms": abs(hash(agent_name)) % 500 + 50,
            }
        else:
            # Build a comparison-oriented prompt
            prompt = (
                f"Task: {task}\n\n"
                f"You are an expert software engineer. Produce the best possible "
                f"implementation. Include:\n"
                f"1. Core logic with clear function/class structure\n"
                f"2. Error handling for edge cases\n"
                f"3. Comments explaining key decisions\n"
                f"4. At least one test or usage example\n\n"
                f"Output complete, runnable code files using the write_file tool."
            )

            agent_dir = os.path.join(session_dir, agent_name)
            os.makedirs(agent_dir, exist_ok=True)

            result = execute(
                agent_name=agent_name,
                agent_config=agent_config,
                task=prompt,
                work_dir=work_dir_root,
                timeout=timeout,
                session_dir=agent_dir,
                stage_prefix=stage_prefix,
            )

        # Score the output
        score_detail = _score_output(result, agent_name)
        result["score"] = score_detail["total"]
        result["score_detail"] = score_detail

        icon = ok() if result.get("success") else fail()
        cprint(f"{icon} {score_detail['total']:.1f} pts — "
               f"{len(result.get('produced_files', []))} files, "
               f"{result.get('duration_ms', 0)}ms")

        results.append(result)

        # Save individual agent summary
        _save_agent_summary(session_dir, agent_name, result, score_detail)

    # ── Rank results ──
    rankings = sorted(results, key=lambda r: r.get("score", 0), reverse=True)
    winner = rankings[0]["agent"] if rankings else "N/A"

    # ── Build summary ──
    summary = _build_comparison_table(results, rankings, winner, task)

    # ── Save overall comparison ──
    _save_comparison(session_dir, task, results, rankings, winner)

    return {
        "results": results,
        "rankings": rankings,
        "winner": winner,
        "session_dir": session_dir,
        "summary": summary,
    }


# ═══════════════════════════════════════════════════════════════
# Scoring
# ═══════════════════════════════════════════════════════════════

def _score_output(result: dict, agent_name: str) -> dict:
    """Score an agent's output on multiple quality dimensions (0-10 each)."""
    stdout = result.get("stdout", "")
    files = result.get("produced_files", [])
    error = result.get("error", "")

    # 1. File count — more files = broader solution (up to 10)
    file_count = len(files)
    file_score = min(file_count * 2.5, 10)

    # 2. Code lines — substance (up to 10)
    total_lines = 0
    for f in files:
        # Count lines roughly from stdout
        total_lines += stdout.count("\n")
    code_score = min(total_lines / 10, 10)

    # 3. Has tests
    has_test_keywords = any(
        kw in stdout.lower()
        for kw in ["test", "assert", "pytest", "unittest", "expect", "spec"]
    ) or any("test" in f.get("path", "").lower() for f in files)
    test_score = 10.0 if has_test_keywords else 0.0

    # 4. Has documentation
    has_doc_keywords = any(
        kw in stdout
        for kw in ["\"\"\"", "'''", "// ", "/* ", "*/", "@param", "@return",
                    "# ", "README", "docstring", "documentation"]
    )
    doc_score = 10.0 if has_doc_keywords else 2.0

    # 5. Error handling
    has_error_handling = any(
        kw in stdout.lower()
        for kw in ["try:", "except", "catch", "error", "raise", "throw",
                    "err != nil", "if err", "result.err"]
    )
    error_score = 10.0 if has_error_handling else 1.0

    # 6. Structure — multiple functions/classes
    structure_count = len(re.findall(
        r'\b(def |class |function |const |export |public )', stdout
    ))
    structure_score = min(structure_count * 2, 10)

    # Weighted total
    weights = SCORE_WEIGHTS
    total = (
        file_score * weights["file_count"] +
        code_score * weights["code_lines"] +
        test_score * weights["has_tests"] +
        doc_score  * weights["has_docs"] +
        error_score * weights["has_errors"] +
        structure_score * weights["structure"]
    ) * 10  # scale to 0-100

    return {
        "total": round(min(total, 100), 1),
        "file_count": round(file_score, 1),
        "code_lines": round(code_score, 1),
        "has_tests": round(test_score, 1),
        "has_docs": round(doc_score, 1),
        "has_errors": round(error_score, 1),
        "structure": round(structure_score, 1),
    }


# ═══════════════════════════════════════════════════════════════
# Display
# ═══════════════════════════════════════════════════════════════

def _build_comparison_table(
    results: list,
    rankings: list,
    winner: str,
    task: str,
) -> str:
    """Build a formatted comparison table for display."""
    lines = [
        bold("\n" + "═" * 70),
        bold("  Multi-Plan Comparison Results"),
        bold("═" * 70),
        "",
        f"  Task:  {task[:80]}",
        f"  Winner: {bold(green('★ ' + winner))}",
        "",
        f"  {'Rank':<6s} {'Agent':<14s} {'Score':<8s} {'Files':<7s} {'Time':<8s} {'Details'}",
        f"  {'─' * 6} {'─' * 14} {'─' * 8} {'─' * 7} {'─' * 8} {'─' * 30}",
    ]

    medals = {0: "🥇", 1: "🥈", 2: "🥉"}

    for rank, r in enumerate(rankings):
        medal = medals.get(rank, f" {rank+1}. ")
        agent = r["agent"]
        score = r.get("score", 0)
        files = len(r.get("produced_files", []))
        dur = f"{r.get('duration_ms', 0)}ms"

        # Color-code score
        if score >= 70:
            score_str = green(f"{score:.1f}")
        elif score >= 40:
            score_str = yellow(f"{score:.1f}")
        else:
            score_str = red(f"{score:.1f}")

        # Detail sparkline from score_detail
        detail = r.get("score_detail", {})
        detail_str = (
            f"L:{detail.get('code_lines', 0):.0f} "
            f"D:{detail.get('has_docs', 0):.0f} "
            f"T:{detail.get('has_tests', 0):.0f} "
            f"E:{detail.get('has_errors', 0):.0f} "
            f"S:{detail.get('structure', 0):.0f}"
        )

        lines.append(
            f"  {medal:<6s} {cyan(agent):<14s} {score_str:<8s} "
            f"{files:<7d} {dim(dur):<8s} {dim(detail_str)}"
        )

    lines.append("")
    lines.append(dim("  Legend: L=codeLines D=docs T=tests E=errorHandling S=structure"))
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Persistence
# ═══════════════════════════════════════════════════════════════

def _save_agent_summary(session_dir: str, agent_name: str, result: dict, score: dict):
    """Save per-agent comparison data."""
    agent_dir = os.path.join(session_dir, agent_name)
    os.makedirs(agent_dir, exist_ok=True)
    summary = {
        "agent": agent_name,
        "success": result.get("success", False),
        "score": score,
        "files": result.get("produced_files", []),
        "stdout_preview": (result.get("stdout", "") or "")[:500],
        "duration_ms": result.get("duration_ms", 0),
    }
    path = os.path.join(agent_dir, "comparison.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def _save_comparison(
    session_dir: str,
    task: str,
    results: list,
    rankings: list,
    winner: str,
):
    """Save the full comparison result."""
    summary = {
        "mode": "multi-plan",
        "task": task,
        "winner": winner,
        "timestamp": datetime.now().isoformat(),
        "agents": len(results),
        "rankings": [
            {
                "rank": i + 1,
                "agent": r["agent"],
                "score": r.get("score", 0),
                "files": len(r.get("produced_files", [])),
                "duration_ms": r.get("duration_ms", 0),
            }
            for i, r in enumerate(rankings)
        ],
    }
    path = os.path.join(session_dir, "comparison_result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    cprint(f"\n  Archive: {dim(session_dir)}")
    cprint(f"  Summary: {dim('comparison_result.json')}")


# ═══════════════════════════════════════════════════════════════
# Mock helpers
# ═══════════════════════════════════════════════════════════════

def _generate_mock_output(agent_name: str) -> str:
    """Generate realistic-looking mock code for comparison testing."""
    templates = {
        "coder": (
            '```python main.py\n'
            '"""Solution with full structure and error handling."""\n'
            'import sys\n\n'
            'class TaskProcessor:\n'
            '    def __init__(self, input_data):\n'
            '        self.data = input_data\n\n'
            '    def process(self):\n'
            '        """Main processing logic."""\n'
            '        if not self.data:\n'
            '            raise ValueError("Empty input")\n'
            '        try:\n'
            '            result = self._transform(self.data)\n'
            '            return {"status": "ok", "result": result}\n'
            '        except Exception as e:\n'
            '            return {"status": "error", "message": str(e)}\n\n'
            '    def _transform(self, data):\n'
            '        return [x * 2 for x in data]\n'
            '```\n\n'
            '```python test_main.py\n'
            'def test_process_valid():\n'
            '    p = TaskProcessor([1, 2, 3])\n'
            '    assert p.process()["status"] == "ok"\n'
            'def test_process_empty():\n'
            '    p = TaskProcessor([])\n'
            '    try: p.process()\n'
            '    except ValueError: pass\n'
            '```'
        ),
        "reviewer": (
            '```python solution.py\n'
            'def solve(data):\n'
            '    """Simple and clean approach."""\n'
            '    if not data:\n'
            '        return []\n'
            '    return [d * 2 for d in data if d > 0]\n'
            '```\n'
            '```python test_solution.py\n'
            'from solution import solve\n'
            'def test_basic(): assert solve([1,2]) == [2,4]\n'
            'def test_empty(): assert solve([]) == []\n'
            '```'
        ),
        "bugfixer": (
            '```python fix.py\n'
            '"""Fixed version with improved error handling."""\n'
            'def process(input_list):\n'
            '    try:\n'
            '        return [x * 2 for x in input_list]\n'
            '    except TypeError:\n'
            '        raise ValueError("Expected list input")\n'
            '```\n'
            '```python test_fix.py\n'
            'import pytest\n'
            'from fix import process\n'
            'def test_ok(): assert process([1,2]) == [2,4]\n'
            'def test_bad(): \n'
            '    with pytest.raises(ValueError):\n'
            '        process("bad")\n'
            '```'
        ),
        "tester": (
            '```python impl.py\n'
            'def compute(values):\n'
            '    return [v * 2 for v in values]\n'
            '```\n'
            '```python test_impl.py\n'
            'import unittest\n'
            'from impl import compute\n'
            'class TestCompute(unittest.TestCase):\n'
            '    def test_basic(self):\n'
            '        self.assertEqual(compute([1,2,3]), [2,4,6])\n'
            '    def test_empty(self):\n'
            '        self.assertEqual(compute([]), [])\n'
            'if __name__ == "__main__":\n'
            '    unittest.main()\n'
            '```'
        ),
    }
    return templates.get(agent_name, templates["coder"])


def _create_mock_files(session_dir: str, agent_name: str, output: str) -> list[dict]:
    """Parse mock output into fake files for scoring."""
    from executor import _extract_code_blocks, _scan_files
    agent_dir = os.path.join(session_dir, agent_name)
    os.makedirs(agent_dir, exist_ok=True)
    extracted = _extract_code_blocks(output, agent_dir)
    scanned = _scan_files(agent_dir)
    seen = {f["path"] for f in scanned}
    for ef in extracted:
        if ef["path"] not in seen:
            scanned.append(ef)
    return scanned

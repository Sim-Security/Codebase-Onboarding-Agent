#!/usr/bin/env python3
"""
Simple eval runner for the Codebase Onboarding Agent.
Tests the agent against defined eval tasks and reports metrics.
"""

import os
import re
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Load .env file
from dotenv import load_dotenv
load_dotenv()

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from src.agent import CodebaseOnboardingAgent


def clone_test_repo(url: str, target: str) -> bool:
    """Clone a test repository."""
    if Path(target).exists():
        shutil.rmtree(target)
    result = subprocess.run(
        ["git", "clone", "--depth=1", url, target],
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def count_citations(text: str) -> int:
    """Count file:line citations in text."""
    pattern = r'[a-zA-Z0-9_/.-]+\.(py|ts|js|tsx|jsx|go|rs|java|rb):\d+'
    matches = re.findall(pattern, text)
    return len(matches)


def count_claims(text: str) -> int:
    """Rough estimate of claims (sentences with technical content)."""
    # Count lines that look like they're making claims
    lines = text.split('\n')
    claim_count = 0
    for line in lines:
        line = line.strip()
        if len(line) > 20 and any(kw in line.lower() for kw in
            ['is', 'uses', 'contains', 'has', 'provides', 'implements', 'handles']):
            claim_count += 1
    return max(claim_count, 1)


def check_hallucinations(text: str, false_claims: list) -> list:
    """Check for known false claims."""
    found = []
    text_lower = text.lower()
    for claim in false_claims:
        if claim.lower() in text_lower:
            found.append(claim)
    return found


def check_required_content(text: str, required: list) -> tuple[int, int]:
    """Check for required content."""
    text_lower = text.lower()
    found = 0
    for item in required:
        if item.lower() in text_lower:
            found += 1
    return found, len(required)


def run_overview_accuracy_eval(agent: CodebaseOnboardingAgent) -> dict:
    """Run the overview accuracy eval."""
    print("\n📊 Running: overview-accuracy")
    print("-" * 40)

    output = agent.get_overview()
    print(f"Output length: {len(output)} chars")

    # Check for hallucinations (Flask should NOT have these)
    false_claims = ["FastAPI", "PostgreSQL", "SQLAlchemy", "Django", "MongoDB"]
    hallucinations = check_hallucinations(output, false_claims)

    # Check for required content (Flask SHOULD have these)
    required = ["Flask", "Python", "Werkzeug", "Jinja"]
    found, total = check_required_content(output, required)

    # Calculate scores
    hallucination_score = 1.0 if not hallucinations else 0.0
    accuracy_score = found / total if total > 0 else 0.0

    result = {
        "task": "overview-accuracy",
        "passed": len(hallucinations) == 0 and found >= 3,
        "hallucinations_found": hallucinations,
        "required_found": f"{found}/{total}",
        "hallucination_score": hallucination_score,
        "accuracy_score": accuracy_score,
        "output_preview": output[:500] + "..." if len(output) > 500 else output
    }

    print(f"  Hallucinations: {hallucinations if hallucinations else 'None ✓'}")
    print(f"  Required content: {found}/{total}")
    print(f"  PASSED: {'✓' if result['passed'] else '✗'}")

    return result


def run_citation_rate_eval(agent: CodebaseOnboardingAgent) -> dict:
    """Run the citation rate eval."""
    print("\n📊 Running: citation-rate")
    print("-" * 40)

    output = agent.ask("How does Flask handle routing?")
    print(f"Output length: {len(output)} chars")

    # Count citations
    citations = count_citations(output)
    claims = count_claims(output)
    citation_rate = citations / claims if claims > 0 else 0.0

    result = {
        "task": "citation-rate",
        "passed": citations >= 3,
        "citations_found": citations,
        "estimated_claims": claims,
        "citation_rate": round(citation_rate * 100, 1),
        "output_preview": output[:500] + "..." if len(output) > 500 else output
    }

    print(f"  Citations found: {citations}")
    print(f"  Estimated claims: {claims}")
    print(f"  Citation rate: {result['citation_rate']}%")
    print(f"  PASSED: {'✓' if result['passed'] else '✗'}")

    return result


def run_tool_usage_eval(agent: CodebaseOnboardingAgent) -> dict:
    """
    Run the tool usage eval.
    Traces actual LangGraph tool calls via the agent's tool call log.
    """
    print("\n📊 Running: tool-usage")
    print("-" * 40)

    # Reset conversation and run overview
    agent.reset_conversation()
    output = agent.get_overview()

    # Get actual tool calls from the agent (traced via LangGraph)
    tool_calls = agent.get_tool_calls()
    tool_names = agent.get_tool_names()

    # Required tools per eval spec
    required_tools = [
        "list_directory_structure",
        "analyze_dependencies",
        "find_entry_points",
    ]

    # Check which required tools were called
    required_found = [t for t in required_tools if t in tool_names]
    required_missing = [t for t in required_tools if t not in tool_names]

    # Calculate tool usage rate (required tools found / total required)
    tool_usage_rate = len(required_found) / len(required_tools) if required_tools else 0

    # Pass if at least 3 tool calls AND at least 2 required tools
    passed = len(tool_calls) >= 3 and len(required_found) >= 2

    result = {
        "task": "tool-usage",
        "passed": passed,
        "total_tool_calls": len(tool_calls),
        "unique_tools_used": tool_names,
        "required_tools_found": required_found,
        "required_tools_missing": required_missing,
        "tool_usage_rate": round(tool_usage_rate * 100, 1),
    }

    print(f"  Total tool calls: {len(tool_calls)}")
    print(f"  Unique tools: {tool_names}")
    print(f"  Required tools found: {required_found}")
    print(f"  Required tools missing: {required_missing}")
    print(f"  Tool usage rate: {result['tool_usage_rate']}%")
    print(f"  PASSED: {'✓' if result['passed'] else '✗'}")

    return result


def main():
    print("=" * 50)
    print("🧪 Codebase Onboarding Agent - Eval Suite")
    print("=" * 50)

    # Setup
    test_repo_url = "https://github.com/pallets/flask"
    test_repo_path = "/tmp/eval-flask"

    print(f"\n📦 Cloning test repo: {test_repo_url}")
    if not clone_test_repo(test_repo_url, test_repo_path):
        print("❌ Failed to clone test repo")
        return
    print("✓ Cloned successfully")

    # Initialize agent
    print("\n🤖 Initializing agent...")
    try:
        agent = CodebaseOnboardingAgent(test_repo_path)
        print("✓ Agent initialized")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        return

    # Run evals
    results = []

    try:
        results.append(run_overview_accuracy_eval(agent))
        agent.reset_conversation()

        results.append(run_citation_rate_eval(agent))
        agent.reset_conversation()

        results.append(run_tool_usage_eval(agent))
    except Exception as e:
        print(f"\n❌ Eval failed with error: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    print("\n" + "=" * 50)
    print("📈 EVAL SUMMARY")
    print("=" * 50)

    passed = sum(1 for r in results if r.get("passed", False))
    total = len(results)

    for r in results:
        status = "✓ PASS" if r.get("passed") else "✗ FAIL"
        print(f"  {r['task']}: {status}")

    print(f"\nOverall: {passed}/{total} passed")

    # Calculate KPIs from Telos
    if results:
        print("\n📊 KPI Measurements (from TELOS.md):")

        # K1: Hallucination rate
        overview_result = next((r for r in results if r["task"] == "overview-accuracy"), None)
        if overview_result:
            hallucination_rate = 0 if overview_result["hallucination_score"] == 1.0 else 100
            print(f"  K1 Hallucination rate: {hallucination_rate}% (target: <5%)")

        # K2: Citation rate
        citation_result = next((r for r in results if r["task"] == "citation-rate"), None)
        if citation_result:
            print(f"  K2 Citation rate: {citation_result['citation_rate']}% (target: >80%)")

        # K3: Tool usage rate
        tool_result = next((r for r in results if r["task"] == "tool-usage"), None)
        if tool_result:
            print(f"  K3 Tool usage rate: {tool_result['tool_usage_rate']}% (target: >90%)")

    # Save results
    results_file = Path(__file__).parent / "evals" / "results.json"
    results_file.parent.mkdir(exist_ok=True)

    report = {
        "timestamp": datetime.now().isoformat(),
        "test_repo": test_repo_url,
        "model": os.getenv("OPENROUTER_MODEL", "x-ai/grok-4.1-fast"),
        "results": results,
        "summary": {
            "passed": passed,
            "total": total,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0
        }
    }

    with open(results_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n📁 Results saved to: {results_file}")

    # Cleanup
    print("\n🧹 Cleaning up...")
    shutil.rmtree(test_repo_path, ignore_errors=True)
    print("✓ Done")


if __name__ == "__main__":
    main()

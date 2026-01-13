#!/usr/bin/env python3
"""
Generate a visual HTML report from eval results.
Makes it easy for humans to understand what was tested and the outcomes.
"""

import json
from pathlib import Path
from datetime import datetime


def load_results():
    """Load the multi-repo eval results."""
    results_file = Path(__file__).parent / "evals" / "multi_repo_results.json"
    if not results_file.exists():
        raise FileNotFoundError("No eval results found. Run `python run_multi_eval.py` first.")
    with open(results_file) as f:
        return json.load(f)


def generate_html_report(data: dict) -> str:
    """Generate an HTML report from eval data."""

    summary = data["summary"]
    results = data["results"]

    # Calculate stats
    total_tests = summary["tests_passed"] + summary["tests_failed"]
    pass_rate = summary["tests_passed"] / total_tests * 100 if total_tests > 0 else 0

    # Build language stats
    lang_rows = ""
    for lang, stats in summary["by_language"].items():
        total = stats["passed"] + stats["failed"]
        pct = stats["passed"] / total * 100 if total > 0 else 0
        status = "pass" if stats["failed"] == 0 else "partial"
        lang_rows += f"""
        <tr class="{status}">
            <td>{lang}</td>
            <td>{stats['passed']}/{total}</td>
            <td>{pct:.1f}%</td>
            <td class="status-cell">{"✅" if stats["failed"] == 0 else "⚠️"}</td>
        </tr>"""

    # Build category stats
    cat_rows = ""
    for cat, stats in summary["by_category"].items():
        total = stats["passed"] + stats["failed"]
        pct = stats["passed"] / total * 100 if total > 0 else 0
        status = "pass" if stats["failed"] == 0 else "partial"
        cat_rows += f"""
        <tr class="{status}">
            <td>{cat.title()}</td>
            <td>{stats['passed']}/{total}</td>
            <td>{pct:.1f}%</td>
            <td class="status-cell">{"✅" if stats["failed"] == 0 else "⚠️"}</td>
        </tr>"""

    # Build individual repo results
    repo_cards = ""
    for r in results:
        status_class = "pass" if r["failed"] == 0 else "fail"
        tests_html = ""

        for test_name, test_result in r.get("tests", {}).items():
            passed = test_result.get("passed", False)
            icon = "✅" if passed else "❌"

            # Build details based on test type
            details = ""
            if test_name == "overview":
                if "tech_accuracy" in test_result:
                    details = f"Tech accuracy: {test_result['tech_accuracy']}%"
                    if test_result.get("hallucinations"):
                        details += f" | Hallucinations: {', '.join(test_result['hallucinations'])}"
                    details += f" | Citations: {test_result.get('citations', 0)}"
                elif "error" in test_result:
                    details = f"Error: {test_result['error'][:50]}..."
            elif test_name == "deep_dive":
                details = f"Citations: {test_result.get('citations', 0)} | Tool calls: {test_result.get('tool_calls', 0)}"
            elif test_name == "language_detection":
                details = f"Expected: {test_result.get('expected', 'N/A')}"

            tests_html += f"""
            <div class="test-item {'test-pass' if passed else 'test-fail'}">
                <span class="test-icon">{icon}</span>
                <span class="test-name">{test_name.replace('_', ' ').title()}</span>
                <span class="test-details">{details}</span>
            </div>"""

        repo_cards += f"""
        <div class="repo-card {status_class}">
            <div class="repo-header">
                <h3>{r['repo']}</h3>
                <span class="repo-meta">{r['language']} • {r['category']}</span>
                <span class="repo-score">{r['passed']}/{r['passed'] + r['failed']}</span>
            </div>
            <div class="repo-tests">
                {tests_html}
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Codebase Onboarding Agent - Eval Report</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}

        h1 {{
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .subtitle {{ text-align: center; color: #888; margin-bottom: 2rem; }}

        .hero-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .stat-value {{ font-size: 2.5rem; font-weight: bold; }}
        .stat-value.green {{ color: #00ff88; }}
        .stat-value.blue {{ color: #00d9ff; }}
        .stat-value.yellow {{ color: #ffd700; }}
        .stat-label {{ color: #888; margin-top: 0.5rem; }}

        .section {{ margin-bottom: 3rem; }}
        .section h2 {{
            font-size: 1.5rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid rgba(255,255,255,0.1);
        }}

        .eval-explainer {{
            background: rgba(0,217,255,0.1);
            border-left: 4px solid #00d9ff;
            padding: 1rem 1.5rem;
            border-radius: 0 8px 8px 0;
            margin-bottom: 2rem;
        }}
        .eval-explainer h3 {{ color: #00d9ff; margin-bottom: 0.5rem; }}
        .eval-explainer p {{ color: #aaa; line-height: 1.6; }}

        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 0.75rem 1rem; text-align: left; }}
        th {{ background: rgba(255,255,255,0.05); color: #00d9ff; }}
        tr {{ border-bottom: 1px solid rgba(255,255,255,0.05); }}
        tr.pass {{ background: rgba(0,255,136,0.05); }}
        tr.partial {{ background: rgba(255,215,0,0.05); }}
        .status-cell {{ text-align: center; font-size: 1.2rem; }}

        .repo-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 1.5rem;
        }}
        .repo-card {{
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .repo-card.pass {{ border-left: 4px solid #00ff88; }}
        .repo-card.fail {{ border-left: 4px solid #ff6b6b; }}
        .repo-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}
        .repo-header h3 {{ color: #fff; }}
        .repo-meta {{ color: #888; font-size: 0.85rem; }}
        .repo-score {{
            background: rgba(0,255,136,0.2);
            color: #00ff88;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-weight: bold;
        }}
        .repo-card.fail .repo-score {{
            background: rgba(255,107,107,0.2);
            color: #ff6b6b;
        }}

        .repo-tests {{ display: flex; flex-direction: column; gap: 0.5rem; }}
        .test-item {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.5rem;
            border-radius: 6px;
            font-size: 0.9rem;
        }}
        .test-pass {{ background: rgba(0,255,136,0.1); }}
        .test-fail {{ background: rgba(255,107,107,0.1); }}
        .test-icon {{ font-size: 1rem; }}
        .test-name {{ font-weight: 500; min-width: 140px; }}
        .test-details {{ color: #888; font-size: 0.8rem; }}

        .footer {{
            text-align: center;
            padding: 2rem;
            color: #666;
            border-top: 1px solid rgba(255,255,255,0.05);
            margin-top: 3rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Codebase Onboarding Agent</h1>
        <p class="subtitle">Comprehensive Evaluation Report</p>

        <div class="hero-stats">
            <div class="stat-card">
                <div class="stat-value green">{pass_rate:.1f}%</div>
                <div class="stat-label">Overall Pass Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value blue">{summary['tests_passed']}/{total_tests}</div>
                <div class="stat-label">Tests Passed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value yellow">{summary['total_repos']}</div>
                <div class="stat-label">Repos Tested</div>
            </div>
            <div class="stat-card">
                <div class="stat-value green">{len(summary['by_language'])}</div>
                <div class="stat-label">Languages</div>
            </div>
        </div>

        <div class="section">
            <h2>📋 What We Test</h2>

            <div class="eval-explainer">
                <h3>1. Overview Accuracy</h3>
                <p>Can the agent correctly identify the project type, tech stack, and architecture?
                We check for <strong>hallucinations</strong> (mentioning technologies that aren't in the codebase)
                and verify expected technologies are found. Every claim must be grounded in actual code.</p>
            </div>

            <div class="eval-explainer">
                <h3>2. Deep Dive Questions</h3>
                <p>When asked specific questions like "How does the entry point work?", does the agent
                <strong>use tools to explore</strong> before answering? We count file:line citations and
                verify the agent actually reads code rather than guessing.</p>
            </div>

            <div class="eval-explainer">
                <h3>3. Language Detection</h3>
                <p>A simple but important check: can the agent correctly identify what programming language
                the project is written in? This validates basic code understanding.</p>
            </div>
        </div>

        <div class="section">
            <h2>📊 Results by Language</h2>
            <table>
                <thead>
                    <tr>
                        <th>Language</th>
                        <th>Tests Passed</th>
                        <th>Pass Rate</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {lang_rows}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>📁 Results by Category</h2>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Tests Passed</th>
                        <th>Pass Rate</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {cat_rows}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>🔬 Individual Repository Results</h2>
            <div class="repo-grid">
                {repo_cards}
            </div>
        </div>

        <div class="footer">
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Model: {data.get('model', 'Unknown')} | Eval timestamp: {data.get('timestamp', 'Unknown')}</p>
        </div>
    </div>
</body>
</html>"""

    return html


def main():
    print("📊 Generating visual eval report...")

    data = load_results()
    html = generate_html_report(data)

    output_file = Path(__file__).parent / "evals" / "report.html"
    with open(output_file, "w") as f:
        f.write(html)

    print(f"✅ Report saved to: {output_file}")
    print(f"   Open in browser: file://{output_file.absolute()}")


if __name__ == "__main__":
    main()

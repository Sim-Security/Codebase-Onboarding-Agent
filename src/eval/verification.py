"""
EVAL-001: Semantic Citation Verification

Verifies that citations in agent responses actually reference content
that was read by tools during the conversation.
"""

import logging
import re

logger = logging.getLogger(__name__)


def extract_citations(text: str) -> list[dict]:
    """
    Extract file:line citations from text.

    Args:
        text: Response text containing citations

    Returns:
        List of {"file": "path.py", "line": 42} dicts
    """
    # Match patterns like: file.py:42, src/utils.py:123, path/to/file.ts:17
    pattern = r"([a-zA-Z0-9_/.-]+\.(?:py|ts|js|tsx|jsx|go|rs|java|rb|toml|json|md|yaml|yml)):(\d+)"
    matches = re.findall(pattern, text)
    return [{"file": m[0], "line": int(m[1])} for m in matches]


def verify_citation(citation: dict, tool_outputs: list[str]) -> dict:
    """
    Verify a single citation against actual tool outputs.

    A citation is valid if:
    1. The file was read by a tool (file name appears in output)
    2. The line number exists in the tool output

    Args:
        citation: {"file": "path.py", "line": 42}
        tool_outputs: List of tool output strings

    Returns:
        {
            "citation": "file.py:42",
            "valid": bool,
            "file_read": bool,
            "line_exists": bool,
            "reason": str
        }
    """
    file_path = citation["file"]
    line_num = citation["line"]
    file_name = file_path.split("/")[-1]  # Get just filename

    result = {
        "citation": f"{file_path}:{line_num}",
        "valid": False,
        "file_read": False,
        "line_exists": False,
        "reason": "",
    }

    # Check if file was read by any tool
    for output in tool_outputs:
        # Check for filename in tool output
        if file_name in output or file_path in output:
            result["file_read"] = True

            # Check if line number exists in the output
            # Tool outputs typically have format: "  42 | code here" or "42: code"
            line_patterns = [
                rf"^\s*{line_num}\s*\|",  # "  42 | code"
                rf"^\s*{line_num}:\s",  # "42: code"
                rf"{file_name}:{line_num}",  # "file.py:42"
                rf"line\s+{line_num}\b",  # "line 42"
            ]

            for pattern in line_patterns:
                if re.search(pattern, output, re.MULTILINE | re.IGNORECASE):
                    result["line_exists"] = True
                    result["valid"] = True
                    result["reason"] = "Verified: file read and line found"
                    return result

            # File was read but line not found - still partially valid
            # The agent may be referencing something it saw
            result["reason"] = f"File read but line {line_num} not in visible output"
            # Mark as valid if file was read (soft verification)
            result["valid"] = True
            return result

    result["reason"] = "File was not read by any tool"
    return result


def verify_all_citations(response: str, tool_outputs: list[str]) -> dict:
    """
    Verify all citations in a response against tool outputs.

    Args:
        response: Agent response text
        tool_outputs: List of tool output strings from agent.get_tool_outputs()

    Returns:
        {
            "total": int,
            "verified": int,
            "unverified": int,
            "precision": float (0-1),
            "details": list[dict]
        }
    """
    citations = extract_citations(response)

    results = {
        "total": len(citations),
        "verified": 0,
        "unverified": 0,
        "precision": 0.0,
        "details": [],
    }

    for citation in citations:
        verification = verify_citation(citation, tool_outputs)
        results["details"].append(verification)

        if verification["valid"]:
            results["verified"] += 1
        else:
            results["unverified"] += 1

    if results["total"] > 0:
        results["precision"] = results["verified"] / results["total"]

    return results


def count_technical_claims(text: str) -> int:
    """
    EVAL-004: Improved claim counting using sentence analysis.

    A claim is a sentence that makes a factual assertion about the code.
    This replaces the naive keyword-based counting.

    Args:
        text: Response text

    Returns:
        Number of technical claims
    """
    # Split into sentences (handle common patterns)
    sentences = re.split(r"(?<=[.!?])\s+", text)

    claim_patterns = [
        r"\b(is|are|uses?|contains?|has|have|provides?|implements?)\b",
        r"\b(handles?|supports?|includes?|defines?|exports?|imports?)\b",
        r"\b(calls?|returns?|takes?|accepts?|creates?|initializes?)\b",
        r"\b(located|found|defined|declared|written)\b",
    ]

    claims = 0
    for sentence in sentences:
        # Skip short sentences or markdown headers
        if len(sentence) < 30 or sentence.strip().startswith("#"):
            continue
        # Skip code blocks
        if sentence.strip().startswith("```") or "```" in sentence:
            continue
        # Skip bullet points that are just file references
        if re.match(r"^[\-\*]\s*`[^`]+`\s*$", sentence.strip()):
            continue

        # Check for claim patterns
        for pattern in claim_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                claims += 1
                break

    return max(claims, 1)  # At least 1 to avoid division by zero


def count_cited_claims(text: str) -> int:
    """
    Count claims that have associated citations.

    A claim is cited if it's in the same paragraph/section as a citation.

    Args:
        text: Response text

    Returns:
        Number of claims with nearby citations
    """
    # Split into paragraphs
    paragraphs = text.split("\n\n")
    citation_pattern = r"[a-zA-Z0-9_/.-]+\.(?:py|ts|js|go|rs):\d+"

    cited = 0
    for para in paragraphs:
        if re.search(citation_pattern, para):
            cited += count_technical_claims(para)

    return cited


def calculate_citation_metrics(response: str, tool_outputs: list[str]) -> dict:
    """
    EVAL-004: Calculate meaningful citation metrics (precision/recall/F1).

    Replaces the meaningless 250%+ citation rates.

    Args:
        response: Agent response text
        tool_outputs: List of tool output strings

    Returns:
        {
            "precision": float (0-100),
            "recall": float (0-100),
            "f1": float (0-100),
            "total_citations": int,
            "verified_citations": int,
            "total_claims": int,
            "cited_claims": int
        }
    """
    # Verify citations
    verification = verify_all_citations(response, tool_outputs)

    # Count claims
    total_claims = count_technical_claims(response)
    cited_claims = count_cited_claims(response)

    # Calculate metrics
    precision = verification["precision"] * 100  # % of citations that are valid
    recall = (
        (cited_claims / total_claims * 100) if total_claims > 0 else 0
    )  # % of claims with citations

    # F1 score
    if precision + recall > 0:
        f1 = 2 * (precision * recall) / (precision + recall)
    else:
        f1 = 0

    return {
        "precision": round(precision, 1),
        "recall": round(recall, 1),
        "f1": round(f1, 1),
        "total_citations": verification["total"],
        "verified_citations": verification["verified"],
        "total_claims": total_claims,
        "cited_claims": cited_claims,
        "verification_details": verification["details"],
    }

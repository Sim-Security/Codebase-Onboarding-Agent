"""Citation verification for grounded responses."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class CitationResult:
    """Result of citation verification."""

    valid: bool
    file_read: bool
    line_exists: bool
    file_path: str
    line_number: Optional[int]
    actual_content: Optional[str] = None
    error: Optional[str] = None


@dataclass
class Claim:
    """A factual claim extracted from a response."""

    text: str
    claim_type: str  # "code_location", "functionality", "structure", "dependency"
    has_citation: bool
    citation: Optional[dict] = None  # {"file": str, "line": int} if cited


@dataclass
class GroundingResult:
    """Result of grounding verification for a claim."""

    claim: Claim
    is_grounded: bool
    citation_result: Optional[CitationResult] = None
    relevance_score: float = 0.0  # 0-1, how relevant citation is to claim
    error: Optional[str] = None


def extract_citations(text: str) -> list[dict]:
    """
    Extract citations from response text.

    Supports formats:
    - file.py:42
    - `file.py:42`
    - (file.py:42)
    - [file.py:42]
    - `file.py`-42 (alternate format some models use)
    - ``file.py`-42`

    Returns:
        List of {"file": str, "line": int}
    """
    citations = []

    # Pattern 1: Standard colon format - file.py:42
    pattern1 = r"[`\[\(]?([a-zA-Z0-9_/.-]+\.[a-zA-Z]+):(\d+)[`\]\)]?"
    for match in re.finditer(pattern1, text):
        file_path = match.group(1)
        line_num = int(match.group(2))
        citations.append({"file": file_path, "line": line_num})

    # Pattern 2: Backtick-hyphen format - `file.py`-42 or ``file.py`-42`
    pattern2 = r"`+([a-zA-Z0-9_/.-]+\.[a-zA-Z]+)`+-(\d+)`?"
    for match in re.finditer(pattern2, text):
        file_path = match.group(1)
        line_num = int(match.group(2))
        # Avoid duplicates
        entry = {"file": file_path, "line": line_num}
        if entry not in citations:
            citations.append(entry)

    return citations


def verify_citation(citation: dict, tool_outputs: list[str]) -> CitationResult:
    """
    Verify a citation against actual tool outputs.

    This performs SEMANTIC verification, not soft verification:
    1. File must have been actually read (appears in tool output)
    2. Line number must exist in the output
    3. Returns detailed result with actual content

    Args:
        citation: {"file": str, "line": int}
        tool_outputs: List of tool output strings from the agent run

    Returns:
        CitationResult with verification details
    """
    file_path = citation.get("file", "")
    line_num = citation.get("line")

    if not file_path:
        return CitationResult(
            valid=False,
            file_read=False,
            line_exists=False,
            file_path=file_path,
            line_number=line_num,
            error="No file path in citation",
        )

    if line_num is None:
        return CitationResult(
            valid=False,
            file_read=False,
            line_exists=False,
            file_path=file_path,
            line_number=None,
            error="No line number in citation",
        )

    # Search through tool outputs
    file_read = False
    for output in tool_outputs:
        # Check if this output contains the file
        # Look for patterns like "📄 filename.py" or "filename.py ("
        file_name = file_path.split("/")[-1]  # Get just the filename

        if file_name not in output and file_path not in output:
            continue

        # Check if this is a read_file output (has 📄 header and line numbers)
        # vs a search result or other tool output
        if f"📄 {file_name}" not in output and f"📄 {file_path}" not in output:
            # This is likely a search result or other reference, not read_file
            # Continue to check other outputs
            continue

        # This is a read_file output - mark as read
        file_read = True

        # Check if line number exists in output
        # Tool outputs format lines as: "   42 | code here"
        line_pattern = rf"^\s*{line_num}\s*\|"

        if re.search(line_pattern, output, re.MULTILINE):
            # Line exists - extract content
            actual_content = extract_line_content(output, line_num)

            return CitationResult(
                valid=True,
                file_read=True,
                line_exists=True,
                file_path=file_path,
                line_number=line_num,
                actual_content=actual_content,
            )
        # If line not found in this read_file output, it truly doesn't exist
        # (the file was read but line number is out of range)
        return CitationResult(
            valid=False,
            file_read=True,
            line_exists=False,
            file_path=file_path,
            line_number=line_num,
            error=f"Line {line_num} not found in file output",
        )

    # File was never read
    return CitationResult(
        valid=False,
        file_read=False,
        line_exists=False,
        file_path=file_path,
        line_number=line_num,
        error="File was not read by any tool",
    )


def extract_line_content(output: str, line_num: int) -> Optional[str]:
    """Extract the content of a specific line from tool output."""
    pattern = rf"^\s*{line_num}\s*\|\s*(.*)$"
    match = re.search(pattern, output, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def verify_all_citations(text: str, tool_outputs: list[str]) -> dict:
    """
    Verify all citations in a response.

    Returns:
        {
            "citations": list[CitationResult],
            "total": int,
            "valid": int,
            "invalid": int,
            "precision": float
        }
    """
    citations = extract_citations(text)
    results = []

    for citation in citations:
        result = verify_citation(citation, tool_outputs)
        results.append(result)

    valid_count = sum(1 for r in results if r.valid)
    total = len(results)

    return {
        "citations": results,
        "total": total,
        "valid": valid_count,
        "invalid": total - valid_count,
        "precision": valid_count / total if total > 0 else 0.0,
    }


def extract_claims(text: str) -> list[Claim]:
    """
    Extract factual claims from agent response.

    Identifies statements that make claims about:
    - Code location ("X is defined in file.py")
    - Functionality ("The function does Y")
    - Structure ("The project uses Z architecture")
    - Dependencies ("Uses library X")

    Filters out:
    - Questions
    - Opinions/hedging ("might", "probably", "seems")
    - Meta-statements ("I found", "Let me check")

    Args:
        text: Agent response text

    Returns:
        List of Claim objects
    """
    claims = []

    # Split into sentences
    sentences = re.split(r"[.!?]\s+", text)

    # Patterns for different claim types
    code_location_patterns = [
        r"(?:is |are )?(?:defined|located|found|implemented|declared) in [`\']?([^`\']+)[`\']?",
        r"in [`\']?([a-zA-Z0-9_/.-]+\.[a-zA-Z]+)[`\']?(?::|,| at)",
        r"file [`\']?([a-zA-Z0-9_/.-]+\.[a-zA-Z]+)[`\']?",
    ]

    functionality_patterns = [
        r"(?:function|method|class) [`\']?(\w+)[`\']? (?:does|handles|processes|returns|takes)",
        r"(?:handles|processes|manages|creates|returns|validates)",
        r"(?:is responsible for|is used to|is called when)",
    ]

    structure_patterns = [
        r"(?:uses?|follows?|implements?) (?:the )?(\w+ (?:pattern|architecture|structure))",
        r"(?:organized|structured) (?:as|into|using)",
        r"(?:entry point|main file|configuration)",
    ]

    dependency_patterns = [
        r"(?:uses?|requires?|depends on|imports?) [`\']?([a-zA-Z0-9_-]+)[`\']?",
        r"(?:built with|powered by|based on)",
    ]

    # Patterns to filter out non-factual statements
    filter_patterns = [
        r"^(?:I |Let me |I\'ll |I\'m )",  # Meta-statements
        r"\?$",  # Questions
        r"(?:might|could|probably|possibly|perhaps|seems?|appears?)",  # Hedging
        r"^(?:Note:|Warning:|Tip:)",  # Advisory statements
    ]

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 10:  # Skip very short fragments
            continue

        # Check if should be filtered
        should_filter = False
        for pattern in filter_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                should_filter = True
                break

        if should_filter:
            continue

        # Determine claim type
        claim_type = None

        for pattern in code_location_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                claim_type = "code_location"
                break

        if not claim_type:
            for pattern in functionality_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    claim_type = "functionality"
                    break

        if not claim_type:
            for pattern in structure_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    claim_type = "structure"
                    break

        if not claim_type:
            for pattern in dependency_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    claim_type = "dependency"
                    break

        if claim_type:
            # Check if sentence has a citation
            citations = extract_citations(sentence)
            has_citation = len(citations) > 0
            citation = citations[0] if citations else None

            claims.append(
                Claim(
                    text=sentence,
                    claim_type=claim_type,
                    has_citation=has_citation,
                    citation=citation,
                )
            )

    return claims


def ground_claims(claims: list[Claim], tool_outputs: list[str]) -> dict:
    """
    Ground claims against tool outputs to verify they are supported.

    For each claim:
    1. If it has a citation, verify the citation
    2. Check if the cited content supports the claim
    3. For claims without citations, check if any tool output supports it

    Args:
        claims: List of Claim objects from extract_claims()
        tool_outputs: List of tool output strings from agent run

    Returns:
        {
            "results": list[GroundingResult],
            "total_claims": int,
            "grounded_claims": int,
            "ungrounded_claims": int,
            "grounding_rate": float,
            "cited_claims": int,
            "uncited_claims": int
        }
    """
    results = []

    for claim in claims:
        if claim.has_citation and claim.citation:
            # Verify the citation
            citation_result = verify_citation(claim.citation, tool_outputs)

            if citation_result.valid:
                # Check if cited content is relevant to claim
                relevance = compute_relevance(
                    claim.text, citation_result.actual_content or ""
                )
                is_grounded = relevance > 0.3  # Threshold for relevance

                results.append(
                    GroundingResult(
                        claim=claim,
                        is_grounded=is_grounded,
                        citation_result=citation_result,
                        relevance_score=relevance,
                    )
                )
            else:
                # Citation invalid
                results.append(
                    GroundingResult(
                        claim=claim,
                        is_grounded=False,
                        citation_result=citation_result,
                        error=citation_result.error,
                    )
                )
        else:
            # No citation - check if any tool output supports the claim
            found_support = False
            best_relevance = 0.0

            for output in tool_outputs:
                relevance = compute_relevance(claim.text, output[:2000])
                if relevance > best_relevance:
                    best_relevance = relevance
                if relevance > 0.4:  # Higher threshold for uncited claims
                    found_support = True
                    break

            results.append(
                GroundingResult(
                    claim=claim,
                    is_grounded=found_support,
                    relevance_score=best_relevance,
                    error="No citation provided" if not found_support else None,
                )
            )

    # Compute statistics
    grounded = sum(1 for r in results if r.is_grounded)
    cited = sum(1 for c in claims if c.has_citation)
    total = len(claims)

    return {
        "results": results,
        "total_claims": total,
        "grounded_claims": grounded,
        "ungrounded_claims": total - grounded,
        "grounding_rate": grounded / total if total > 0 else 0.0,
        "cited_claims": cited,
        "uncited_claims": total - cited,
    }


def compute_relevance(claim_text: str, content: str) -> float:
    """
    Compute relevance score between claim and content.

    Uses keyword overlap as a simple heuristic.
    Higher scores = more relevant.

    Args:
        claim_text: The claim being verified
        content: Content that should support the claim

    Returns:
        Relevance score 0-1
    """
    if not claim_text or not content:
        return 0.0

    # Extract keywords (words 4+ chars, excluding common words)
    stopwords = {
        "that",
        "this",
        "with",
        "from",
        "have",
        "which",
        "there",
        "their",
        "about",
        "would",
        "could",
        "should",
    }

    claim_words = set(re.findall(r"\b\w{4,}\b", claim_text.lower())) - stopwords
    content_words = set(re.findall(r"\b\w{4,}\b", content.lower())) - stopwords

    if not claim_words:
        return 0.5  # Can't determine, give benefit of doubt

    overlap = claim_words & content_words
    relevance = len(overlap) / len(claim_words)

    return min(relevance, 1.0)


def calculate_citation_metrics(response: str, tool_outputs: list[str]) -> dict:
    """
    Calculate comprehensive citation metrics for a response.

    Combines citation verification with claim grounding to produce
    precision, recall, and F1 metrics.

    Args:
        response: The agent's text response
        tool_outputs: List of tool output strings from the agent run

    Returns:
        {
            "total_citations": int,
            "verified_citations": int,
            "invalid_citations": int,
            "precision": float,  # valid citations / total citations
            "total_claims": int,
            "grounded_claims": int,
            "grounding_rate": float,  # grounded / total claims
            "recall": float,  # same as grounding_rate
            "f1": float  # harmonic mean of precision and recall
        }
    """
    # Verify all citations
    citation_results = verify_all_citations(response, tool_outputs)

    # Extract and ground claims
    claims = extract_claims(response)
    grounding = ground_claims(claims, tool_outputs)

    # Precision: valid citations / total citations
    precision = citation_results["precision"]

    # Recall: grounded claims / total claims (how well are claims supported)
    recall = grounding["grounding_rate"]

    # F1: harmonic mean
    if precision + recall > 0:
        f1 = 2 * (precision * recall) / (precision + recall)
    else:
        f1 = 0.0

    return {
        "total_citations": citation_results["total"],
        "verified_citations": citation_results["valid"],
        "invalid_citations": citation_results["invalid"],
        "precision": round(precision, 3),
        "total_claims": grounding["total_claims"],
        "grounded_claims": grounding["grounded_claims"],
        "grounding_rate": round(grounding["grounding_rate"], 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


def filter_ungrounded_citations(
    response: str, tool_outputs: list[str], add_warning: bool = True
) -> tuple[str, int]:
    """
    Remove ungrounded citations from a response.

    Replaces citations that can't be verified against tool outputs with
    just the file name (no line number) and optionally adds a warning.

    Args:
        response: The agent's text response
        tool_outputs: List of tool output strings from the agent run
        add_warning: Whether to add a warning about removed citations

    Returns:
        (filtered_response, num_removed)
    """
    citations = extract_citations(response)
    if not citations:
        return response, 0

    filtered = response
    removed_count = 0

    for citation in citations:
        result = verify_citation(citation, tool_outputs)
        if not result.valid:
            # Replace the citation with just the filename
            file_path = citation.get("file", "")
            line_num = citation.get("line", 0)

            # Match various citation formats (including backtick-hyphen format)
            patterns = [
                rf"`{re.escape(file_path)}:{line_num}`",
                rf"\[{re.escape(file_path)}:{line_num}\]",
                rf"\({re.escape(file_path)}:{line_num}\)",
                rf"{re.escape(file_path)}:{line_num}",
                # Backtick-hyphen format: ``file.py`-42`
                rf"``{re.escape(file_path)}`-{line_num}`",
                rf"`{re.escape(file_path)}`-{line_num}",
            ]

            for pattern in patterns:
                if re.search(pattern, filtered):
                    # Replace with just filename (no line)
                    filtered = re.sub(pattern, f"`{file_path}`", filtered, count=1)
                    removed_count += 1
                    break

    if removed_count > 0 and add_warning:
        warning = (
            f"\n\n*Note: {removed_count} unverified line references were simplified.*"
        )
        if warning not in filtered:
            filtered += warning

    return filtered, removed_count


def get_grounded_citations_only(response: str, tool_outputs: list[str]) -> list[dict]:
    """
    Return only the citations that can be verified against tool outputs.

    Args:
        response: The agent's text response
        tool_outputs: List of tool output strings

    Returns:
        List of verified citations
    """
    citations = extract_citations(response)
    grounded = []

    for citation in citations:
        result = verify_citation(citation, tool_outputs)
        if result.valid:
            grounded.append(citation)

    return grounded


def get_files_read_from_tool_calls(tool_calls: list[dict]) -> set[str]:
    """
    Extract file paths from all read_file tool calls.

    Args:
        tool_calls: List of tool call dictionaries with format:
                    {"name": str, "args": dict} where args contains "file_path"

    Returns:
        Set of file paths that were actually read via read_file tool
    """
    files_read = set()

    for tc in tool_calls:
        tool_name = tc.get("name", "")
        if tool_name == "read_file":
            args = tc.get("args", {})
            if isinstance(args, dict):
                file_path = args.get("file_path", "")
                if file_path:
                    files_read.add(file_path)

    return files_read


@dataclass
class ToolUsageValidationResult:
    """Result of tool usage validation."""

    has_read_file: bool
    files_read_count: int
    citations_count: int
    valid: bool
    files_read: set[str]
    cited_files: set[str]
    unread_cited_files: set[str]


def validate_tool_usage(tool_calls: list[dict], response: str) -> dict:
    """
    Validate that read_file was called before citations appear in the response.

    This function checks that the agent properly read files before citing them,
    which is critical for grounded responses. Citations from files that were
    never read via read_file are considered invalid.

    Args:
        tool_calls: List of tool call dictionaries from the agent run.
                    Format: {"name": str, "args": dict}
        response: The agent's final text response

    Returns:
        {
            "has_read_file": bool,       # True if any read_file calls were made
            "files_read_count": int,     # Number of unique files read
            "citations_count": int,      # Number of citations in response
            "valid": bool,               # True if citations are properly grounded
            "files_read": list[str],     # List of files that were read
            "cited_files": list[str],    # List of files cited in response
            "unread_cited_files": list[str]  # Files cited but never read
        }
    """
    # Get files read via read_file tool
    files_read = get_files_read_from_tool_calls(tool_calls)

    # Extract citations from response
    citations = extract_citations(response)
    citations_count = len(citations)

    # Get unique cited files (extract just the filename for comparison)
    cited_files = set()
    for citation in citations:
        file_path = citation.get("file", "")
        if file_path:
            cited_files.add(file_path)

    # Determine which cited files were not read
    # We need to handle both full paths and relative paths
    unread_cited_files = set()
    for cited_file in cited_files:
        # Check if cited file matches any read file (exact or as suffix)
        file_was_read = False
        cited_basename = cited_file.split("/")[-1]

        for read_file in files_read:
            read_basename = read_file.split("/")[-1]
            # Match if exact path, or if the basenames match and cited is a suffix
            if (
                read_file == cited_file
                or read_file.endswith(cited_file)
                or cited_file.endswith(read_file)
                or cited_basename == read_basename
            ):
                file_was_read = True
                break

        if not file_was_read:
            unread_cited_files.add(cited_file)

    # Validation passes if:
    # 1. No citations exist (nothing to validate), OR
    # 2. read_file was called AND no cited files are unread
    has_read_file = len(files_read) > 0
    valid = citations_count == 0 or (has_read_file and len(unread_cited_files) == 0)

    return {
        "has_read_file": has_read_file,
        "files_read_count": len(files_read),
        "citations_count": citations_count,
        "valid": valid,
        "files_read": list(files_read),
        "cited_files": list(cited_files),
        "unread_cited_files": list(unread_cited_files),
    }


@dataclass
class ProjectIdentityResult:
    """Result of project identity validation."""

    valid: bool
    expected_name: str
    expected_type: str
    name_found: bool
    type_correct: bool
    error: Optional[str] = None


def validate_project_identity(response: str, repo_metadata: dict) -> bool:
    """
    Validate that the response correctly identifies the project.

    This function checks whether the agent correctly identifies:
    1. The project name (from package metadata files)
    2. The project type (CLI vs web vs library)

    Args:
        response: The agent's text response
        repo_metadata: Dictionary with project metadata:
                       {"name": str, "type": str}
                       - name: The actual project name from metadata files
                       - type: One of "cli", "web", "library", "unknown"

    Returns:
        True if the response correctly identifies the project, False otherwise
    """
    expected_name = repo_metadata.get("name", "").lower()
    expected_type = repo_metadata.get("type", "unknown").lower()

    if not expected_name:
        # No name to validate against
        return True

    response_lower = response.lower()

    # Check 1: Does the response mention the correct project name?
    name_found = expected_name in response_lower

    # Check 2: Does the response describe the correct project type?
    type_correct = True  # Default to True if type is unknown

    if expected_type == "cli":
        # CLI projects should NOT be described as web frameworks
        web_indicators = [
            "web framework",
            "web application",
            "http server",
            "rest api",
            "web server",
            "handles http requests",
            "routes http",
            "web development",
        ]
        cli_indicators = [
            "cli",
            "command-line",
            "command line",
            "terminal",
            "commandline",
            "cli framework",
            "cli tool",
            "cli library",
        ]

        # Fail if response describes it as a web framework
        has_web_description = any(ind in response_lower for ind in web_indicators)
        has_cli_description = any(ind in response_lower for ind in cli_indicators)

        # It's wrong if it says it's a web framework OR if it doesn't mention CLI
        if has_web_description:
            type_correct = False
        elif not has_cli_description:
            # No CLI description found - might be a hallucination
            type_correct = False

    elif expected_type == "web":
        # Web projects should NOT be described as CLI tools
        cli_indicators = [
            "cli tool",
            "command-line interface",
            "terminal application",
            "cli framework",
            "command line tool",
        ]
        web_indicators = [
            "web",
            "http",
            "server",
            "api",
            "routes",
            "framework",
        ]

        has_cli_description = any(ind in response_lower for ind in cli_indicators)
        has_web_description = any(ind in response_lower for ind in web_indicators)

        if has_cli_description:
            type_correct = False
        elif not has_web_description:
            type_correct = False

    # Both checks must pass
    return name_found and type_correct


def get_project_identity_details(
    response: str, repo_metadata: dict
) -> ProjectIdentityResult:
    """
    Get detailed results of project identity validation.

    Similar to validate_project_identity but returns detailed information
    about what passed and what failed.

    Args:
        response: The agent's text response
        repo_metadata: Dictionary with project metadata:
                       {"name": str, "type": str}

    Returns:
        ProjectIdentityResult with validation details
    """
    expected_name = repo_metadata.get("name", "").lower()
    expected_type = repo_metadata.get("type", "unknown").lower()

    if not expected_name:
        return ProjectIdentityResult(
            valid=True,
            expected_name="",
            expected_type=expected_type,
            name_found=True,
            type_correct=True,
        )

    response_lower = response.lower()
    name_found = expected_name in response_lower

    type_correct = True
    error = None

    if expected_type == "cli":
        web_indicators = [
            "web framework",
            "web application",
            "http server",
            "rest api",
            "web server",
        ]
        cli_indicators = [
            "cli",
            "command-line",
            "command line",
            "terminal",
        ]

        has_web = any(ind in response_lower for ind in web_indicators)
        has_cli = any(ind in response_lower for ind in cli_indicators)

        if has_web:
            type_correct = False
            error = f"Response describes CLI project '{expected_name}' as a web framework"
        elif not has_cli:
            type_correct = False
            error = f"Response does not identify '{expected_name}' as a CLI tool"

    elif expected_type == "web":
        cli_indicators = [
            "cli tool",
            "command-line interface",
            "terminal application",
            "cli framework",
        ]
        web_indicators = ["web", "http", "server", "api", "routes"]

        has_cli = any(ind in response_lower for ind in cli_indicators)
        has_web = any(ind in response_lower for ind in web_indicators)

        if has_cli:
            type_correct = False
            error = f"Response describes web project '{expected_name}' as a CLI tool"
        elif not has_web:
            type_correct = False
            error = f"Response does not identify '{expected_name}' as a web framework"

    if not name_found and error is None:
        error = f"Response does not mention project name '{expected_name}'"

    return ProjectIdentityResult(
        valid=name_found and type_correct,
        expected_name=expected_name,
        expected_type=expected_type,
        name_found=name_found,
        type_correct=type_correct,
        error=error,
    )

"""
Parser for converting agent responses into structured insights.

Handles various response formats (JSON, markdown, plain text) and
extracts structured insight data for storage.
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# Valid severity levels
VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}
DEFAULT_SEVERITY = "info"


def parse_insights(
    content: str,
    category: str,
    expected_format: str = "json"
) -> List[Dict[str, Any]]:
    """
    Parse agent response into structured insights.

    Args:
        content: Raw response content from the agent
        category: The analysis category (security, database, etc.)
        expected_format: Expected output format (json, text, markdown)

    Returns:
        List of insight dictionaries ready for database insertion
    """
    if not content or not content.strip():
        logger.warning(f"Empty content received for category {category}")
        return []

    # Try JSON parsing first (most common expected format)
    insights = _try_parse_json(content)

    if insights is None:
        # Try extracting JSON from markdown code blocks
        insights = _try_extract_json_from_markdown(content)

    if insights is None:
        # Try parsing as structured text
        insights = _try_parse_structured_text(content, category)

    if insights is None:
        # Fallback: create a single insight from the entire content
        logger.warning(f"Could not parse structured insights for {category}, using fallback")
        insights = _create_fallback_insight(content, category)

    # Validate and normalize each insight
    normalized = []
    for insight in insights:
        normalized_insight = _normalize_insight(insight, category)
        if normalized_insight:
            normalized.append(normalized_insight)

    logger.info(f"Parsed {len(normalized)} insights for category {category}")
    return normalized


def _try_parse_json(content: str) -> Optional[List[Dict]]:
    """Try to parse content as JSON array."""
    try:
        # Try direct JSON parse
        parsed = json.loads(content.strip())
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            # Single insight as dict
            return [parsed]
    except json.JSONDecodeError:
        pass
    return None


def _try_extract_json_from_markdown(content: str) -> Optional[List[Dict]]:
    """Extract JSON from markdown code blocks."""
    # Look for ```json ... ``` or ``` ... ``` blocks
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            try:
                parsed = json.loads(match.strip())
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict):
                    return [parsed]
            except json.JSONDecodeError:
                continue

    # Try to find JSON array pattern in content
    json_array_pattern = r'\[\s*\{[\s\S]*?\}\s*\]'
    matches = re.findall(json_array_pattern, content)
    for match in matches:
        try:
            parsed = json.loads(match)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed
        except json.JSONDecodeError:
            continue

    return None


def _try_parse_structured_text(
    content: str,
    category: str
) -> Optional[List[Dict]]:
    """
    Try to parse structured text format.

    Looks for patterns like:
    - **Title**: Description
    - Severity: high
    - File: path/to/file.py
    """
    insights = []

    # Split by common section delimiters
    sections = re.split(r'\n(?=#{1,3}\s|\*\*\d+\.|\d+\.\s+\*\*)', content)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        insight = _extract_insight_from_section(section, category)
        if insight and insight.get("title"):
            insights.append(insight)

    return insights if insights else None


def _extract_insight_from_section(section: str, category: str) -> Optional[Dict]:
    """Extract insight data from a text section."""
    insight = {"category": category}

    # Extract title (first line or header)
    lines = section.strip().split('\n')
    first_line = lines[0].strip()

    # Remove markdown headers
    title = re.sub(r'^#+\s*', '', first_line)
    title = re.sub(r'^\*\*\d+\.\s*', '', title)
    title = re.sub(r'\*\*$', '', title)
    title = title.strip()

    if title:
        insight["title"] = title[:500]  # Truncate to max length

    # Extract severity
    severity_match = re.search(
        r'severity[:\s]+(\w+)',
        section,
        re.IGNORECASE
    )
    if severity_match:
        insight["severity"] = severity_match.group(1).lower()

    # Extract file path
    file_match = re.search(
        r'(?:file|path|location)[:\s]+[`"]?([^\s`"]+)[`"]?',
        section,
        re.IGNORECASE
    )
    if file_match:
        insight["file_path"] = file_match.group(1)

    # Extract line numbers
    line_match = re.search(
        r'line[s]?[:\s]+(\d+)(?:\s*[-–]\s*(\d+))?',
        section,
        re.IGNORECASE
    )
    if line_match:
        insight["line_start"] = int(line_match.group(1))
        if line_match.group(2):
            insight["line_end"] = int(line_match.group(2))

    # Extract description (rest of content after title)
    if len(lines) > 1:
        desc_lines = []
        for line in lines[1:]:
            # Skip metadata lines
            if re.match(r'^(severity|file|path|location|line|recommended|fix)[:\s]', line, re.IGNORECASE):
                continue
            desc_lines.append(line)
        if desc_lines:
            insight["description"] = '\n'.join(desc_lines).strip()

    # Extract recommendation
    rec_match = re.search(
        r'(?:recommended?|fix|action|solution)[:\s]+(.+?)(?:\n|$)',
        section,
        re.IGNORECASE | re.DOTALL
    )
    if rec_match:
        insight["recommended_action"] = rec_match.group(1).strip()

    return insight if insight.get("title") else None


def _create_fallback_insight(content: str, category: str) -> List[Dict]:
    """Create a fallback insight when parsing fails."""
    # Truncate content for title
    title = content[:200].split('\n')[0].strip()
    if len(title) > 100:
        title = title[:97] + "..."

    return [{
        "category": category,
        "severity": "info",
        "title": f"Analysis Result: {title}" if title else f"{category.title()} Analysis Complete",
        "description": content[:5000] if len(content) > 5000 else content,
        "details": {"raw_content": True, "parsing_failed": True}
    }]


def _normalize_insight(insight: Dict, category: str) -> Optional[Dict]:
    """
    Normalize and validate an insight dictionary.

    Ensures all required fields are present and valid.
    """
    if not isinstance(insight, dict):
        return None

    normalized = {}

    # Required: category
    normalized["category"] = insight.get("category", category)

    # Required: severity (validate)
    severity = str(insight.get("severity", DEFAULT_SEVERITY)).lower()
    normalized["severity"] = severity if severity in VALID_SEVERITIES else DEFAULT_SEVERITY

    # Required: title
    title = insight.get("title", "")
    if not title:
        return None  # Skip insights without titles
    normalized["title"] = str(title)[:500]

    # Optional: description
    description = insight.get("description")
    if description:
        normalized["description"] = str(description)

    # Optional: file_path
    file_path = insight.get("file_path") or insight.get("file")
    if file_path:
        normalized["file_path"] = str(file_path)[:1000]

    # Optional: line numbers
    line_start = insight.get("line_start") or insight.get("lineStart") or insight.get("line")
    if line_start:
        try:
            normalized["line_start"] = int(line_start)
        except (ValueError, TypeError):
            pass

    line_end = insight.get("line_end") or insight.get("lineEnd")
    if line_end:
        try:
            normalized["line_end"] = int(line_end)
        except (ValueError, TypeError):
            pass

    # Optional: recommended_action
    rec_action = (
        insight.get("recommended_action") or
        insight.get("recommendedAction") or
        insight.get("recommendation") or
        insight.get("fix")
    )
    if rec_action:
        normalized["recommended_action"] = str(rec_action)

    # Optional: code_suggestion
    code_suggestion = (
        insight.get("code_suggestion") or
        insight.get("codeSuggestion") or
        insight.get("code") or
        insight.get("suggestedFix")
    )
    if code_suggestion:
        normalized["code_suggestion"] = str(code_suggestion)

    # Optional: confidence_score
    confidence = insight.get("confidence_score") or insight.get("confidence")
    if confidence is not None:
        try:
            confidence_float = float(confidence)
            if 0 <= confidence_float <= 1:
                normalized["confidence_score"] = confidence_float
        except (ValueError, TypeError):
            pass

    # Optional: details (extra metadata)
    details = insight.get("details")
    if isinstance(details, dict):
        normalized["details"] = details

    return normalized


def extract_insights_summary(insights: List[Dict]) -> Dict[str, Any]:
    """
    Generate a summary of parsed insights.

    Args:
        insights: List of normalized insight dictionaries

    Returns:
        Summary dictionary with counts by severity and category
    """
    summary = {
        "total": len(insights),
        "by_severity": {},
        "by_category": {}
    }

    for insight in insights:
        severity = insight.get("severity", DEFAULT_SEVERITY)
        category = insight.get("category", "unknown")

        summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
        summary["by_category"][category] = summary["by_category"].get(category, 0) + 1

    return summary

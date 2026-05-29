"""File content diff extraction module for weekly report agent.

Provides functions to compare file contents and extract changes
in formats suitable for LLM analysis.
"""

import difflib
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum number of diff lines to output
MAX_DIFF_LINES = 50


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_file_diff(
    old_content: Optional[str],
    new_content: Optional[str],
) -> Dict:
    """Compare old and new file content, returning a structured diff result.

    Parameters
    ----------
    old_content : str or None
        Original file content. None or empty string treated as empty.
    new_content : str or None
        New file content. None or empty string treated as empty.

    Returns
    -------
    dict
        A dictionary containing:
        - ``added_lines``: list of newly added lines (without ``+`` prefix).
        - ``removed_lines``: list of removed lines (without ``-`` prefix).
        - ``diff_text``: unified diff text (limited to MAX_DIFF_LINES).
        - ``has_changes``: bool indicating whether content differs.
        - ``change_summary``: human-readable summary string.
    """
    old_lines = _to_lines(old_content)
    new_lines = _to_lines(new_content)

    diff = list(
        difflib.unified_diff(old_lines, new_lines, lineterm="")
    )

    added_lines: List[str] = []
    removed_lines: List[str] = []
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed_lines.append(line[1:])

    has_changes = len(added_lines) > 0 or len(removed_lines) > 0

    # Build diff text with line limit
    diff_text = "\n".join(diff[:MAX_DIFF_LINES])
    if len(diff) > MAX_DIFF_LINES:
        diff_text += f"\n... (truncated, {len(diff) - MAX_DIFF_LINES} more lines)"

    change_summary = _build_summary(added_lines, removed_lines)

    return {
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "diff_text": diff_text,
        "has_changes": has_changes,
        "change_summary": change_summary,
    }


def extract_changes_for_analysis(
    file_path: str,
    old_content: Optional[str],
    new_content: Optional[str],
) -> str:
    """Extract file changes formatted for LLM analysis.

    Handles three scenarios:
    - New file (old_content is empty): returns full new content.
    - Deleted file (new_content is empty): returns deletion notice.
    - Modified file: returns unified diff.

    Parameters
    ----------
    file_path : str
        Path of the file being compared.
    old_content : str or None
        Original file content.
    new_content : str or None
        New file content.

    Returns
    -------
    str
        Formatted change description suitable for LLM consumption.
    """
    old_is_empty = not old_content or not old_content.strip()
    new_is_empty = not new_content or not new_content.strip()

    # --- New file ---
    if old_is_empty and not new_is_empty:
        lines = new_content.strip().splitlines()
        truncated = lines[:MAX_DIFF_LINES]
        header = f"[New File] {file_path}\n"
        body = "\n".join(truncated)
        if len(lines) > MAX_DIFF_LINES:
            body += f"\n... ({len(lines) - MAX_DIFF_LINES} more lines)"
        return header + body

    # --- Deleted file ---
    if not old_is_empty and new_is_empty:
        return f"[Deleted File] {file_path} (file has been removed)"

    # --- Modified file ---
    diff_result = get_file_diff(old_content, new_content)

    if not diff_result["has_changes"]:
        return ""

    header = f"[Modified File] {file_path}\n"
    summary = f"Summary: {diff_result['change_summary']}\n"
    body = diff_result["diff_text"]

    return header + summary + body


def compare_file_contents(
    old_files: Dict[str, str],
    new_files: Dict[str, str],
) -> Dict[str, Dict]:
    """Compare two sets of file contents and return diffs for changed files.

    Parameters
    ----------
    old_files : dict[str, str]
        Mapping of file_path -> old_content.
    new_files : dict[str, str]
        Mapping of file_path -> new_content.

    Returns
    -------
    dict[str, dict]
        Mapping of file_path -> diff result (only for files with changes).
    """
    all_paths = set(old_files.keys()) | set(new_files.keys())
    results: Dict[str, Dict] = {}

    for path in sorted(all_paths):
        old = old_files.get(path)
        new = new_files.get(path)
        diff_result = get_file_diff(old, new)
        if diff_result["has_changes"]:
            results[path] = diff_result

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_lines(content: Optional[str]) -> List[str]:
    """Convert content string to a list of lines, treating None as empty."""
    if not content:
        return []
    return content.splitlines()


def _build_summary(added: List[str], removed: List[str]) -> str:
    """Build a short human-readable change summary."""
    parts: List[str] = []
    if added:
        parts.append(f"新增 {len(added)} 行")
    if removed:
        parts.append(f"删除 {len(removed)} 行")
    return "，".join(parts) if parts else "无变更"

"""Sensitive information detection module for weekly report agent.

Scans text content for patterns that may indicate leaked secrets,
personal information, or other sensitive data before it is sent to
an LLM for analysis.
"""

import re
from typing import Dict, List


# ---------------------------------------------------------------------------
# Built-in detection patterns
# ---------------------------------------------------------------------------

_DEFAULT_PATTERNS: Dict[str, str] = {
    "API_KEY": (
        r"(?:api[_-]?key|access[_-]?token|secret[_-]?key)"
        r"[=:]\s*['\"]?([a-zA-Z0-9_-]{20,})"
    ),
    "PASSWORD": (
        r"(?:password|passwd|pwd)[=:]\s*['\"]?([^\s'\"]+)"
    ),
    "EMAIL": (
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}"
    ),
    "PHONE": (
        r"(?:\+?1[-.]?)?(?:\(?\d{3}\)?[-.]?)\d{3}[-.]?\d{4}"
    ),
    "PRIVATE_KEY": (
        r"-----BEGIN (?:RSA|EC|OPENSSH|PGP) PRIVATE KEY-----"
    ),
}


class SensitivityDetector:
    """Scan text for potentially sensitive information.

    The detector uses regular-expression patterns to identify common
    categories of sensitive data such as API keys, passwords, email
    addresses, phone numbers, and private-key headers.

    Parameters
    ----------
    extra_patterns : dict[str, str] | None
        Additional ``{label: regex}`` patterns to merge with the
        built-in set.  Keys already present in the defaults will be
        overridden.
    """

    def __init__(self, extra_patterns: Dict[str, str] | None = None):
        self.patterns: Dict[str, str] = dict(_DEFAULT_PATTERNS)
        if extra_patterns:
            self.patterns.update(extra_patterns)

        # Pre-compile for performance
        self._compiled: Dict[str, re.Pattern[str]] = {
            label: re.compile(pattern, re.IGNORECASE)
            for label, pattern in self.patterns.items()
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_text(self, text: str) -> List[Dict]:
        """Scan *text* and return a list of findings.

        Each finding is a dict with the following keys:

        - ``category`` – the pattern label (e.g. ``"API_KEY"``)
        - ``snippet``  – a short excerpt around the match
        - ``position`` – ``(start, end)`` character offsets

        Parameters
        ----------
        text : str
            The text to scan.

        Returns
        -------
        list[dict]
            Detected sensitive-information findings.
        """
        findings: List[Dict] = []
        if not text:
            return findings

        for label, compiled in self._compiled.items():
            for match in compiled.finditer(text):
                start, end = match.start(), match.end()
                # Build a context snippet (max ~60 chars around the match)
                ctx_start = max(0, start - 20)
                ctx_end = min(len(text), end + 20)
                snippet = text[ctx_start:ctx_end]
                # Truncate the matched value itself so we don't echo secrets
                snippet = self._redact_snippet(snippet)
                findings.append(
                    {
                        "category": label,
                        "snippet": snippet,
                        "position": (start, end),
                    }
                )
        return findings

    def get_warning_message(self, findings: List[Dict]) -> str:
        """Generate a human-readable warning from *findings*.

        Parameters
        ----------
        findings : list[dict]
            Output of :meth:`scan_text`.

        Returns
        -------
        str
            A multi-line warning summarising detected categories and counts.
        """
        if not findings:
            return ""

        # Count occurrences per category
        counts: Dict[str, int] = {}
        for f in findings:
            cat = f["category"]
            counts[cat] = counts.get(cat, 0) + 1

        lines = [
            "⚠️  检测到以下敏感信息，请确认是否继续导入：",
            "",
        ]
        for cat, count in sorted(counts.items()):
            lines.append(f"  - {cat}: {count} 处")

        lines.append("")
        lines.append("建议在导入前清理敏感数据，或确认这些内容不会泄露。")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _redact_snippet(snippet: str) -> str:
        """Partially mask the snippet to avoid echoing full secrets."""
        if len(snippet) <= 20:
            return snippet
        # Keep first 10 and last 10 chars, mask the middle
        return snippet[:10] + "…" + snippet[-10:]

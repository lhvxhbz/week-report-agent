"""Git commit history data source for weekly report agent.

Retrieves recent Git commits from a local repository and converts them
into the standardised item format used by the report pipeline.
"""

import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from core.data_source import DataSource


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# git-log field separator unlikely to appear in commit messages
_FIELD_SEP = "§§§"
_RECORD_SEP = "|||"

# git-log format: hash, author, date (ISO), subject, body
_LOG_FORMAT = _FIELD_SEP.join([
    "%H",      # commit hash
    "%an",     # author name
    "%aI",     # author date (ISO 8601)
    "%s",      # subject
    "%b",      # body
])


class GitSource(DataSource):
    """Git commit history data source.

    Reads the Git log of a local repository and returns each commit as
    a standardised work item suitable for LLM analysis.

    Parameters
    ----------
    repo_path : str
        Path to the Git repository root (may be relative).
    """

    source_type: str = "git"
    display_name: str = "Git提交记录"

    def __init__(self, repo_path: str):
        self.repo_path: str = str(Path(repo_path).resolve())

    # ------------------------------------------------------------------
    # DataSource interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether *repo_path* is inside a Git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.repo_path,
                capture_output=True,
                timeout=10,
            )
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            return result.returncode == 0 and "true" in stdout.lower()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    def fetch(self, days: int = 7, **kwargs) -> List[Dict]:
        """Fetch commits from the last *days* days.

        Parameters
        ----------
        days : int
            Number of days of history to retrieve (default 7).
        **kwargs
            ``author`` (str) – filter by author name (substring match).

        Returns
        -------
        list[dict]
            Standardised item dicts.  See :mod:`core.data_source` for the
            schema.

        Raises
        ------
        RuntimeError
            If the ``git log`` command fails.
        """
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        cmd = [
            "git", "log",
            f"--since={since}",
            f"--format={_LOG_FORMAT}{_RECORD_SEP}",
            "--no-merges",
        ]

        # Optional author filter
        author = kwargs.get("author")
        if author:
            cmd.append(f"--author={author}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("git log command timed out (30 s)")
        except FileNotFoundError:
            raise RuntimeError("Git is not installed or not on PATH")

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"git log failed (exit {result.returncode}): {stderr}"
            )

        stdout = result.stdout.decode("utf-8", errors="replace")
        return self._parse_log(stdout)

    def get_sensitivity_warning(self) -> str:
        """Git commits may contain secrets in diffs or messages."""
        return (
            "Git提交记录可能包含敏感信息（如API密钥、密码等），"
            "请确认是否继续导入？"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_log(self, raw: str) -> List[Dict]:
        """Parse raw ``git log`` output into standardised items."""
        items: List[Dict] = []
        if not raw.strip():
            return items

        records = raw.split(_RECORD_SEP)
        for record in records:
            record = record.strip()
            if not record:
                continue

            parts = record.split(_FIELD_SEP)
            if len(parts) < 4:
                continue  # Malformed record – skip

            commit_hash = parts[0].strip()
            author = parts[1].strip()
            date_str = parts[2].strip()
            subject = parts[3].strip()
            body = parts[4].strip() if len(parts) > 4 else ""

            # Format timestamp for display
            timestamp = self._format_timestamp(date_str)

            # Build content for LLM analysis
            content_parts = [f"提交信息: {subject}"]
            if body:
                content_parts.append(f"详细描述: {body}")
            content = "\n".join(content_parts)

            items.append({
                "source_type": self.source_type,
                "title": f"[{commit_hash[:8]}] {subject}",
                "content": content,
                "metadata": {
                    "commit_hash": commit_hash,
                    "author": author,
                    "date": date_str,
                },
                "timestamp": timestamp,
            })

        return items

    @staticmethod
    def _format_timestamp(iso_str: str) -> str:
        """Convert an ISO 8601 timestamp to ``YYYY-MM-DD HH:MM``."""
        try:
            # Handle timezone-aware ISO strings
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            # Fallback: return as-is if parsing fails
            return iso_str[:16] if len(iso_str) >= 16 else iso_str

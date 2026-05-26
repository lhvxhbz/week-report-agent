"""Jira task data source for weekly report agent.

Retrieves recently updated Jira issues using the ``jira`` Python library
and converts them into the standardised item format used by the report
pipeline.

Requires a Jira Cloud/Server URL, a username, and an API token.
See https://id.atlassian.com/manage-profile/security/api-tokens for tokens.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.data_source import DataSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# JQL date format used by Jira
_JQL_DATE_FMT = "%Y-%m-%d"

# Default fields to retrieve
_DEFAULT_FIELDS = [
    "summary",
    "description",
    "status",
    "assignee",
    "reporter",
    "priority",
    "created",
    "updated",
    "resolutiondate",
    "issuetype",
    "labels",
    "components",
]


class JiraSource(DataSource):
    """Jira task data source.

    Fetches issues that have been updated in the last *days* days from a
    Jira instance.

    Parameters
    ----------
    url : str
        Jira instance URL (e.g. ``"https://yourteam.atlassian.net"``).
    username : str
        Jira username (usually the email address).
    api_token : str
        Jira API token (not the password).
    project_key : str, optional
        If provided, restrict queries to this Jira project.
    """

    source_type: str = "jira"
    display_name: str = "Jira"

    def __init__(
        self,
        url: str,
        username: str,
        api_token: str,
        project_key: Optional[str] = None,
    ):
        self.url: str = url.rstrip("/")
        self.username: str = username
        self.api_token: str = api_token
        self.project_key: Optional[str] = project_key

    # ------------------------------------------------------------------
    # DataSource interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether Jira configuration is complete and SDK is installed."""
        if not self.url or not self.username or not self.api_token:
            logger.warning("Jira configuration is incomplete (url/username/api_token)")
            return False

        try:
            from jira import JIRA  # noqa: F401
        except ImportError:
            logger.warning("jira library is not installed. Run: pip install jira")
            return False

        return True

    def fetch(self, days: int = 7, **kwargs: Any) -> List[Dict]:
        """Fetch Jira issues updated in the last *days* days.

        Parameters
        ----------
        days : int
            Number of days of history to retrieve (default 7).
        **kwargs
            ``max_results`` (int) – maximum number of issues to return
            (default 100).
            ``jql_extra`` (str) – additional JQL conditions to append.

        Returns
        -------
        list[dict]
            Standardised item dicts.  See :mod:`core.data_source` for the
            schema.

        Raises
        ------
        RuntimeError
            If the Jira API call fails.
        """
        max_results: int = kwargs.get("max_results", 100)
        jql_extra: str = kwargs.get("jql_extra", "")

        jql = self._build_jql(days, jql_extra)
        logger.info("Jira JQL query: %s", jql)

        client = self._connect()

        try:
            issues = client.search_issues(
                jql,
                maxResults=max_results,
                fields=",".join(_DEFAULT_FIELDS),
                expand="changelog",
            )
        except Exception as exc:
            raise RuntimeError(f"Jira search failed: {exc}") from exc

        logger.info("Fetched %d issues from Jira", len(issues))
        return [self._issue_to_item(issue) for issue in issues]

    def get_sensitivity_warning(self) -> str:
        """Jira issues may contain internal project details."""
        return (
            "Jira任务可能包含项目内部信息、任务描述、负责人等敏感内容，"
            "请确认是否继续导入？"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self):
        """Establish a connection to the Jira instance."""
        from jira import JIRA

        try:
            client = JIRA(
                server=self.url,
                basic_auth=(self.username, self.api_token),
            )
            logger.debug("Connected to Jira at %s", self.url)
            return client
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to Jira at {self.url}: {exc}") from exc

    def _build_jql(self, days: int, extra: str = "") -> str:
        """Build a JQL query string for recent issues."""
        since = (datetime.now() - timedelta(days=days)).strftime(_JQL_DATE_FMT)

        parts = [f'updated >= "{since}"']

        if self.project_key:
            parts.append(f'project = "{self.project_key}"')

        if extra:
            parts.append(f"({extra})")

        return " AND ".join(parts) + " ORDER BY updated DESC"

    def _issue_to_item(self, issue) -> Dict:
        """Convert a raw Jira issue to a standardised item."""
        fields = issue.fields

        summary = fields.summary or "(无标题)"
        description = fields.description or ""

        # Status
        status_name = fields.status.name if fields.status else "Unknown"

        # Priority
        priority_name = fields.priority.name if fields.priority else "None"

        # Assignee
        assignee_name = ""
        if fields.assignee:
            assignee_name = getattr(fields.assignee, "displayName", "") or \
                            getattr(fields.assignee, "name", "")

        # Issue type
        issue_type = fields.issuetype.name if fields.issuetype else "Task"

        # Labels
        labels = list(fields.labels) if fields.labels else []

        # Components
        components = [c.name for c in fields.components] if fields.components else []

        # Dates
        created = fields.created or ""
        updated = fields.updated or ""
        resolved = fields.resolutiondate or ""

        # Build content for LLM analysis
        content_parts = [
            f"[{issue.key}] {summary}",
            f"类型: {issue_type}",
            f"状态: {status_name}",
            f"优先级: {priority_name}",
        ]
        if assignee_name:
            content_parts.append(f"负责人: {assignee_name}")
        if description:
            # Truncate very long descriptions
            desc_preview = description[:500]
            if len(description) > 500:
                desc_preview += "..."
            content_parts.append(f"描述: {desc_preview}")
        if labels:
            content_parts.append(f"标签: {', '.join(labels)}")
        if components:
            content_parts.append(f"组件: {', '.join(components)}")
        if resolved:
            content_parts.append(f"解决时间: {resolved}")

        content = "\n".join(content_parts)

        # Status mapping to standard values
        status_lower = status_name.lower()
        if "done" in status_lower or "resolved" in status_lower or "closed" in status_lower:
            std_status = "done"
        elif "progress" in status_lower or "review" in status_lower:
            std_status = "in_progress"
        else:
            std_status = "todo"

        # URL
        issue_url = f"{self.url}/browse/{issue.key}"

        return {
            "source_type": self.source_type,
            "title": f"[{issue.key}] {summary}",
            "content": content,
            "metadata": {
                "issue_key": issue.key,
                "issue_type": issue_type,
                "status": status_name,
                "std_status": std_status,
                "priority": priority_name,
                "assignee": assignee_name,
                "labels": labels,
                "components": components,
                "created": created,
                "updated": updated,
                "resolved": resolved,
                "url": issue_url,
            },
            "timestamp": self._format_timestamp(updated),
        }

    @staticmethod
    def _format_timestamp(iso_str: str) -> str:
        """Convert an ISO 8601 timestamp to ``YYYY-MM-DD HH:MM``."""
        if not iso_str:
            return ""
        try:
            # Jira returns timestamps like "2024-01-15T10:30:00.000+0800"
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return iso_str[:16] if len(iso_str) >= 16 else iso_str

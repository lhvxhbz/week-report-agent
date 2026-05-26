"""Notion task data source for weekly report agent.

Retrieves database entries from Notion using the ``notion-client`` library
and converts them into the standardised item format used by the report
pipeline.

Requires a Notion integration token and a target database ID.
See https://developers.notion.com/docs/getting-started for setup.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.data_source import DataSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Notion API page size (max 100)
_PAGE_SIZE = 100

# Common date property names to try when extracting timestamps
_DATE_PROPERTY_NAMES = [
    "Date", "date", "日期",
    "Due Date", "due_date", "截止日期",
    "Created", "created_time", "创建时间",
    "Updated", "updated_time", "更新时间",
    "Last edited", "last_edited_time",
]

# Common status property names
_STATUS_PROPERTY_NAMES = [
    "Status", "status", "状态",
    "State", "state",
]

# Common title property names
_TITLE_PROPERTY_NAMES = [
    "Name", "name", "名称",
    "Title", "title", "标题",
    "Task", "task", "任务",
]


class NotionSource(DataSource):
    """Notion task data source.

    Fetches pages from a Notion database and converts them to standardised
    work items.  Works with any Notion database regardless of its schema,
    though it provides the best experience when common property names are
    used (e.g. "Name", "Status", "Date").

    Parameters
    ----------
    token : str
        Notion integration token (starts with ``"ntn_"`` or ``"secret_"``).
    database_id : str
        ID of the Notion database to query.
    filter_property : str, optional
        Name of a date property to filter by.  If not provided, the source
        will auto-detect a date property from the database schema.
    """

    source_type: str = "notion"
    display_name: str = "Notion"

    def __init__(
        self,
        token: str,
        database_id: str,
        filter_property: Optional[str] = None,
    ):
        self.token: str = token
        self.database_id: str = database_id
        self.filter_property: Optional[str] = filter_property

    # ------------------------------------------------------------------
    # DataSource interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether Notion configuration is complete and SDK is installed."""
        if not self.token or not self.database_id:
            logger.warning("Notion token or database_id is not configured")
            return False

        try:
            from notion_client import Client  # noqa: F401
        except ImportError:
            logger.warning(
                "notion-client is not installed. Run: pip install notion-client"
            )
            return False

        return True

    def fetch(self, days: int = 7, **kwargs: Any) -> List[Dict]:
        """Fetch Notion database pages from the last *days* days.

        The source queries pages whose date property falls within the
        specified time range.  If no date property is found, all pages
        are returned (up to ``max_results``).

        Parameters
        ----------
        days : int
            Number of days of history to retrieve (default 7).
        **kwargs
            ``max_results`` (int) – maximum number of pages to return
            (default 200).
            ``filter_json`` (dict) – additional Notion filter to apply
            (AND-ed with the date filter).

        Returns
        -------
        list[dict]
            Standardised item dicts.  See :mod:`core.data_source` for the
            schema.

        Raises
        ------
        RuntimeError
            If the Notion API call fails.
        """
        max_results: int = kwargs.get("max_results", 200)
        extra_filter: Optional[Dict] = kwargs.get("filter_json")

        client = self._connect()

        # Try to find a date property for filtering
        date_prop = self._detect_date_property(client)

        # Build filter
        notion_filter = self._build_filter(days, date_prop, extra_filter)

        # Paginate through results
        all_items: List[Dict] = []
        has_more = True
        start_cursor: Optional[str] = None

        while has_more and len(all_items) < max_results:
            query_params: Dict[str, Any] = {
                "database_id": self.database_id,
                "page_size": min(_PAGE_SIZE, max_results - len(all_items)),
            }
            if notion_filter:
                query_params["filter"] = notion_filter
            if start_cursor:
                query_params["start_cursor"] = start_cursor

            try:
                response = client.databases.query(**query_params)
            except Exception as exc:
                raise RuntimeError(f"Notion database query failed: {exc}") from exc

            pages = response.get("results", [])
            for page in pages:
                all_items.append(self._page_to_item(page, date_prop))

            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

        logger.info("Fetched %d pages from Notion database", len(all_items))
        return all_items

    def get_sensitivity_warning(self) -> str:
        """Notion pages may contain personal notes and project details."""
        return (
            "Notion数据库可能包含个人笔记、项目详情、内部文档等敏感信息，"
            "请确认是否继续导入？"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self):
        """Create and return a Notion API client."""
        from notion_client import Client

        try:
            client = Client(auth=self.token)
            logger.debug("Connected to Notion API")
            return client
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to Notion API: {exc}") from exc

    def _detect_date_property(self, client) -> Optional[str]:
        """Auto-detect a date property from the database schema.

        Returns the property name if found, ``None`` otherwise.
        """
        if self.filter_property:
            return self.filter_property

        try:
            db = client.databases.retrieve(database_id=self.database_id)
            properties = db.get("properties", {})

            # Try common date property names first
            for name in _DATE_PROPERTY_NAMES:
                if name in properties:
                    prop_type = properties[name].get("type", "")
                    if prop_type in ("date", "created_time", "last_edited_time"):
                        logger.debug("Auto-detected date property: %s", name)
                        return name

            # Fallback: find any date-type property
            for name, prop_def in properties.items():
                if prop_def.get("type") in ("date", "created_time", "last_edited_time"):
                    logger.debug("Auto-detected date property: %s", name)
                    return name

        except Exception as exc:
            logger.warning("Failed to retrieve database schema: %s", exc)

        logger.debug("No date property found; will not filter by date")
        return None

    def _build_filter(
        self,
        days: int,
        date_prop: Optional[str],
        extra_filter: Optional[Dict],
    ) -> Optional[Dict]:
        """Build a Notion filter dict for the query."""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        filters: List[Dict] = []

        # Date range filter
        if date_prop:
            # Check if it's a computed property (created_time / last_edited_time)
            # Those use "timestamp" filter, not "date" filter
            filters.append({
                "property": date_prop,
                "date": {
                    "on_or_after": since,
                },
            })

        # Additional user-supplied filter
        if extra_filter:
            filters.append(extra_filter)

        if not filters:
            return None
        if len(filters) == 1:
            return filters[0]
        return {"and": filters}

    def _page_to_item(self, page: Dict, date_prop: Optional[str]) -> Dict:
        """Convert a raw Notion page to a standardised item."""
        properties = page.get("properties", {})
        page_id = page.get("id", "")
        page_url = page.get("url", "")

        # Extract title
        title = self._extract_title(properties)

        # Extract status
        status = self._extract_status(properties)

        # Extract date
        timestamp = self._extract_date(properties, date_prop, page)

        # Extract rich text content from properties
        content_parts = [f"标题: {title}"]
        if status:
            content_parts.append(f"状态: {status}")

        # Extract all text-like properties for content
        for prop_name, prop_def in properties.items():
            prop_type = prop_def.get("type", "")
            if prop_type == "rich_text":
                text = self._get_rich_text(prop_def.get("rich_text", []))
                if text and prop_name.lower() not in ("name", "title", "标题", "名称"):
                    content_parts.append(f"{prop_name}: {text}")
            elif prop_type == "select" and prop_def.get("select"):
                sel_name = prop_def["select"].get("name", "")
                if sel_name:
                    content_parts.append(f"{prop_name}: {sel_name}")
            elif prop_type == "multi_select":
                selections = [s.get("name", "") for s in prop_def.get("multi_select", [])]
                if selections:
                    content_parts.append(f"{prop_name}: {', '.join(selections)}")

        content = "\n".join(content_parts)

        return {
            "source_type": self.source_type,
            "title": title,
            "content": content,
            "metadata": {
                "page_id": page_id,
                "status": status,
                "url": page_url,
                "database_id": self.database_id,
            },
            "timestamp": timestamp,
        }

    def _extract_title(self, properties: Dict) -> str:
        """Extract the title text from Notion properties."""
        # Try common title property names
        for name in _TITLE_PROPERTY_NAMES:
            if name in properties:
                prop = properties[name]
                prop_type = prop.get("type", "")
                if prop_type == "title":
                    return self._get_rich_text(prop.get("title", []))

        # Fallback: find any title-type property
        for prop_def in properties.values():
            if prop_def.get("type") == "title":
                return self._get_rich_text(prop_def.get("title", []))

        return "(无标题)"

    def _extract_status(self, properties: Dict) -> str:
        """Extract the status value from Notion properties."""
        for name in _STATUS_PROPERTY_NAMES:
            if name in properties:
                prop = properties[name]
                prop_type = prop.get("type", "")
                if prop_type == "status" and prop.get("status"):
                    return prop["status"].get("name", "")
                elif prop_type == "select" and prop.get("select"):
                    return prop["select"].get("name", "")

        return ""

    def _extract_date(
        self,
        properties: Dict,
        date_prop: Optional[str],
        page: Dict,
    ) -> str:
        """Extract a date string from Notion properties or page metadata."""
        # Try the detected date property
        if date_prop and date_prop in properties:
            prop = properties[date_prop]
            prop_type = prop.get("type", "")

            if prop_type == "date" and prop.get("date"):
                return prop["date"].get("start", "")
            elif prop_type == "created_time":
                return prop.get("created_time", "")
            elif prop_type == "last_edited_time":
                return prop.get("last_edited_time", "")

        # Fallback: use page-level timestamps
        last_edited = page.get("last_edited_time", "")
        if last_edited:
            return last_edited

        created = page.get("created_time", "")
        if created:
            return created

        return ""

    @staticmethod
    def _get_rich_text(rich_text_list: List[Dict]) -> str:
        """Concatenate Notion rich text segments into a plain string."""
        parts = []
        for segment in rich_text_list:
            text = segment.get("plain_text", "")
            if text:
                parts.append(text)
        return "".join(parts)

    @staticmethod
    def _format_timestamp(iso_str: str) -> str:
        """Convert an ISO 8601 timestamp to ``YYYY-MM-DD HH:MM``."""
        if not iso_str:
            return ""
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return iso_str[:16] if len(iso_str) >= 16 else iso_str

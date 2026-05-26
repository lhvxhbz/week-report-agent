"""Feishu (Lark) data source for weekly report agent.

Retrieves calendar events and tasks from Feishu via the ``lark-oapi`` SDK
and converts them into the standardised item format used by the report
pipeline.

Requires a Feishu application with ``app_id`` and ``app_secret``.
See https://open.feishu.cn/document/home/index for setup.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.data_source import DataSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Feishu API base URL (China region)
_FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"

# Scopes required: calendar:calendar:readonly, task:task:readonly


class FeishuSource(DataSource):
    """Feishu (Lark) data source for calendar events and tasks.

    Uses the ``lark-oapi`` SDK to fetch data from Feishu's Calendar and
    Task APIs.

    Parameters
    ----------
    app_id : str
        Feishu application ID.
    app_secret : str
        Feishu application secret.
    """

    source_type: str = "feishu"
    display_name: str = "飞书"

    def __init__(self, app_id: str, app_secret: str):
        self.app_id: str = app_id
        self.app_secret: str = app_secret
        self._client = None

    # ------------------------------------------------------------------
    # DataSource interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether app_id / app_secret are configured and SDK is installed."""
        if not self.app_id or not self.app_secret:
            logger.warning("Feishu app_id or app_secret is not configured")
            return False

        try:
            import lark_oapi  # noqa: F401
        except ImportError:
            logger.warning(
                "lark-oapi is not installed. Run: pip install lark-oapi"
            )
            return False

        return True

    def fetch(self, days: int = 7, **kwargs: Any) -> List[Dict]:
        """Fetch Feishu calendar events and tasks from the last *days* days.

        Parameters
        ----------
        days : int
            Number of days of history to retrieve (default 7).
        **kwargs
            ``include_calendar`` (bool) – fetch calendar events (default True).
            ``include_tasks`` (bool) – fetch tasks (default True).

        Returns
        -------
        list[dict]
            Standardised item dicts.  See :mod:`core.data_source` for the
            schema.

        Raises
        ------
        RuntimeError
            If the Feishu API calls fail.
        """
        include_calendar: bool = kwargs.get("include_calendar", True)
        include_tasks: bool = kwargs.get("include_tasks", True)

        items: List[Dict] = []

        if include_calendar:
            try:
                calendar_items = self._fetch_calendar_events(days)
                items.extend(calendar_items)
                logger.info("Fetched %d calendar events from Feishu", len(calendar_items))
            except Exception as exc:
                logger.error("Failed to fetch Feishu calendar events: %s", exc)
                raise RuntimeError(f"Feishu calendar fetch failed: {exc}") from exc

        if include_tasks:
            try:
                task_items = self._fetch_tasks(days)
                items.extend(task_items)
                logger.info("Fetched %d tasks from Feishu", len(task_items))
            except Exception as exc:
                logger.error("Failed to fetch Feishu tasks: %s", exc)
                raise RuntimeError(f"Feishu task fetch failed: {exc}") from exc

        return items

    def get_sensitivity_warning(self) -> str:
        """Feishu data may contain meeting details and task descriptions."""
        return (
            "飞书数据可能包含会议详情、任务描述、参与人等敏感信息，"
            "请确认是否继续导入？"
        )

    # ------------------------------------------------------------------
    # Client management
    # ------------------------------------------------------------------

    def _get_client(self):
        """Lazily initialise and return the Feishu API client."""
        if self._client is not None:
            return self._client

        import lark_oapi as lark

        self._client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(lark.LogLevel.WARNING) \
            .build()

        return self._client

    def _get_tenant_access_token(self) -> str:
        """Obtain a tenant access token for API calls."""
        import lark_oapi as lark
        from lark_oapi.api.auth.v3 import (
            CreateTenantAccessTokenRequest,
            CreateTenantAccessTokenRequestBody,
        )

        request = (
            CreateTenantAccessTokenRequest.builder()
            .request_body(
                CreateTenantAccessTokenRequestBody.builder()
                .app_id(self.app_id)
                .app_secret(self.app_secret)
                .build()
            )
            .build()
        )

        client = self._get_client()
        response = client.auth.v3.tenant_access_token.create(request)

        if not response.success():
            raise RuntimeError(
                f"Failed to obtain Feishu tenant token: "
                f"code={response.code}, msg={response.msg}"
            )

        return response.tenant_access_token

    # ------------------------------------------------------------------
    # Calendar fetching
    # ------------------------------------------------------------------

    def _fetch_calendar_events(self, days: int) -> List[Dict]:
        """Fetch calendar events using the Feishu Calendar API."""
        import lark_oapi as lark
        from lark_oapi.api.calendar.v3 import (
            ListCalendarEventRequest,
        )

        now = datetime.now(timezone.utc)
        start_ts = str(int((now - timedelta(days=days)).timestamp()))
        end_ts = str(int(now.timestamp()))

        client = self._get_client()

        # First, get the primary calendar ID
        calendar_id = self._get_primary_calendar_id(client)

        # Fetch events
        request = (
            ListCalendarEventRequest.builder()
            .calendar_id(calendar_id)
            .start_time(start_ts)
            .end_time(end_ts)
            .page_size(50)
            .build()
        )

        all_events: List[Dict] = []
        page_token: Optional[str] = None

        while True:
            if page_token:
                request = (
                    ListCalendarEventRequest.builder()
                    .calendar_id(calendar_id)
                    .start_time(start_ts)
                    .end_time(end_ts)
                    .page_size(50)
                    .page_token(page_token)
                    .build()
                )

            response = client.calendar.v3.calendar_event.list(request)

            if not response.success():
                raise RuntimeError(
                    f"Feishu calendar API error: "
                    f"code={response.code}, msg={response.msg}"
                )

            items = response.data.items if response.data and response.data.items else []
            for event in items:
                all_events.append(self._event_to_item(event))

            # Check for more pages
            if response.data and response.data.has_more:
                page_token = response.data.page_token
            else:
                break

        return all_events

    def _get_primary_calendar_id(self, client) -> str:
        """Get the primary calendar ID for the authenticated user."""
        from lark_oapi.api.calendar.v3 import ListCalendarRequest

        request = ListCalendarRequest.builder().page_size(10).build()
        response = client.calendar.v3.calendar.list(request)

        if not response.success():
            raise RuntimeError(
                f"Feishu calendar list error: "
                f"code={response.code}, msg={response.msg}"
            )

        calendars = response.data.calendar_list if response.data else []
        for cal in calendars:
            if cal.type == "primary" or (cal.calendar_id and "primary" in cal.calendar_id):
                return cal.calendar_id

        # Fallback: use the first available calendar
        if calendars:
            return calendars[0].calendar_id

        raise RuntimeError("No Feishu calendar found for the authenticated user")

    def _event_to_item(self, event) -> Dict:
        """Convert a raw Feishu calendar event to a standardised item."""
        summary = event.summary if hasattr(event, "summary") and event.summary else "(无标题)"
        description = event.description if hasattr(event, "description") and event.description else ""
        location = event.location.name if hasattr(event, "location") and event.location and hasattr(event.location, "name") else ""

        # Extract timestamps
        start_time = ""
        end_time = ""
        if hasattr(event, "start_time") and event.start_time:
            ts = event.start_time.timestamp if hasattr(event.start_time, "timestamp") else ""
            if ts:
                start_time = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
        if hasattr(event, "end_time") and event.end_time:
            ts = event.end_time.timestamp if hasattr(event.end_time, "timestamp") else ""
            if ts:
                end_time = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()

        # Build content
        content_parts = [f"事件: {summary}"]
        if description:
            content_parts.append(f"描述: {description}")
        if location:
            content_parts.append(f"地点: {location}")
        if start_time:
            content_parts.append(f"开始时间: {start_time}")
        if end_time:
            content_parts.append(f"结束时间: {end_time}")

        content = "\n".join(content_parts)
        event_id = event.event_id if hasattr(event, "event_id") else ""

        return {
            "source_type": self.source_type,
            "title": summary,
            "content": content,
            "metadata": {
                "event_id": event_id,
                "location": location,
                "start_time": start_time,
                "end_time": end_time,
                "data_type": "calendar_event",
            },
            "timestamp": self._format_timestamp(start_time),
        }

    # ------------------------------------------------------------------
    # Task fetching
    # ------------------------------------------------------------------

    def _fetch_tasks(self, days: int) -> List[Dict]:
        """Fetch tasks using the Feishu Task API."""
        from lark_oapi.api.task.v2 import ListTaskRequest

        client = self._get_client()

        request = (
            ListTaskRequest.builder()
            .page_size(50)
            .build()
        )

        all_tasks: List[Dict] = []
        page_token: Optional[str] = None
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        while True:
            if page_token:
                request = (
                    ListTaskRequest.builder()
                    .page_size(50)
                    .page_token(page_token)
                    .build()
                )

            response = client.task.v2.task.list(request)

            if not response.success():
                raise RuntimeError(
                    f"Feishu task API error: "
                    f"code={response.code}, msg={response.msg}"
                )

            items = response.data.items if response.data and response.data.items else []
            for task in items:
                item = self._task_to_item(task)
                # Filter by time range
                task_ts = item.get("timestamp", "")
                if task_ts:
                    try:
                        task_dt = datetime.strptime(task_ts, "%Y-%m-%d %H:%M")
                        task_dt = task_dt.replace(tzinfo=timezone.utc)
                        if task_dt < cutoff:
                            continue
                    except ValueError:
                        pass  # Include if we can't parse the date
                all_tasks.append(item)

            # Check for more pages
            if response.data and response.data.has_more:
                page_token = response.data.page_token
            else:
                break

        return all_tasks

    def _task_to_item(self, task) -> Dict:
        """Convert a raw Feishu task to a standardised item."""
        title = task.summary if hasattr(task, "summary") and task.summary else "(无标题)"
        description = task.description if hasattr(task, "description") and task.description else ""

        # Status mapping
        status_map = {
            0: "todo",
            1: "in_progress",
            2: "done",
        }
        raw_status = task.status if hasattr(task, "status") and task.status else None
        status_val = raw_status.status if hasattr(raw_status, "status") else 0
        status = status_map.get(status_val, "unknown")

        # Completion time or update time
        completed_at = ""
        if hasattr(task, "completed_at") and task.completed_at:
            ts = task.completed_at.timestamp if hasattr(task.completed_at, "timestamp") else ""
            if ts:
                completed_at = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()

        updated_at = ""
        if hasattr(task, "updated_at") and task.updated_at:
            ts = task.updated_at.timestamp if hasattr(task.updated_at, "timestamp") else ""
            if ts:
                updated_at = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()

        # Build content
        content_parts = [f"任务: {title}"]
        if description:
            content_parts.append(f"描述: {description}")
        content_parts.append(f"状态: {status}")
        if completed_at:
            content_parts.append(f"完成时间: {completed_at}")

        content = "\n".join(content_parts)
        task_id = task.guid if hasattr(task, "guid") else ""
        timestamp = completed_at or updated_at

        return {
            "source_type": self.source_type,
            "title": title,
            "content": content,
            "metadata": {
                "task_id": task_id,
                "status": status,
                "completed_at": completed_at,
                "data_type": "task",
            },
            "timestamp": self._format_timestamp(timestamp),
        }

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

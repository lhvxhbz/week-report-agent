"""Google Calendar data source for weekly report agent.

Retrieves calendar events from Google Calendar via the Google Calendar API
and converts them into the standardised item format used by the report
pipeline.

Requires a Google Cloud service-account or OAuth credentials JSON file.
See https://developers.google.com/calendar/quickstart/python for setup.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.data_source import DataSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
_PRIMARY = "primary"


class GoogleCalendarSource(DataSource):
    """Google Calendar data source.

    Fetches events from Google Calendar using the ``google-api-python-client``
    library and a local credentials file (service-account or OAuth client).

    Parameters
    ----------
    credentials_path : str
        Path to the Google API credentials JSON file.
    token_path : str, optional
        Path to the OAuth2 token file (for installed-app flow).  If not
        provided, the service-account flow is used instead.
    calendar_id : str, optional
        Calendar ID to fetch events from.  Defaults to ``"primary"``.
    """

    source_type: str = "google_calendar"
    display_name: str = "Google日历"

    def __init__(
        self,
        credentials_path: str,
        token_path: Optional[str] = None,
        calendar_id: str = _PRIMARY,
    ):
        self.credentials_path: str = credentials_path
        self.token_path: Optional[str] = token_path
        self.calendar_id: str = calendar_id

    # ------------------------------------------------------------------
    # DataSource interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether the credentials file exists and the SDK is installed."""
        cred_path = Path(self.credentials_path)
        if not cred_path.exists():
            logger.warning("Google Calendar credentials file not found: %s", cred_path)
            return False

        try:
            from google.oauth2 import service_account  # noqa: F401
            from googleapiclient.discovery import build  # noqa: F401
        except ImportError:
            logger.warning(
                "google-api-python-client or google-auth is not installed. "
                "Run: pip install google-api-python-client google-auth-httplib2"
            )
            return False

        return True

    def fetch(self, days: int = 7, **kwargs: Any) -> List[Dict]:
        """Fetch calendar events from the last *days* days.

        Parameters
        ----------
        days : int
            Number of days of history to retrieve (default 7).
        **kwargs
            ``max_results`` (int) – maximum number of events to return
            (default 250).

        Returns
        -------
        list[dict]
            Standardised item dicts.  See :mod:`core.data_source` for the
            schema.

        Raises
        ------
        RuntimeError
            If the Google Calendar API call fails.
        """
        max_results: int = kwargs.get("max_results", 250)

        now = datetime.now(timezone.utc)
        time_min = (now - timedelta(days=days)).isoformat()
        time_max = now.isoformat()

        service = self._build_service()

        try:
            events_result = (
                service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except Exception as exc:
            raise RuntimeError(f"Google Calendar API request failed: {exc}") from exc

        events = events_result.get("items", [])
        logger.info("Fetched %d events from Google Calendar", len(events))

        return [self._event_to_item(event) for event in events]

    def get_sensitivity_warning(self) -> str:
        """Calendar events may contain meeting links and attendee info."""
        return (
            "日历事件可能包含会议链接、参会人员等敏感信息，"
            "请确认是否继续导入？"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_service(self):
        """Build and return a Google Calendar API service object."""
        from googleapiclient.discovery import build

        credentials = self._get_credentials()
        return build("calendar", "v3", credentials=credentials)

    def _get_credentials(self):
        """Obtain Google API credentials from the configured source."""
        from google.oauth2 import service_account

        cred_path = Path(self.credentials_path)

        # Service-account flow (preferred for server-to-server)
        if self.token_path is None:
            logger.debug("Using service-account credentials: %s", cred_path)
            return service_account.Credentials.from_service_account_file(
                str(cred_path), scopes=_SCOPES
            )

        # OAuth installed-app flow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        token_path = Path(self.token_path)
        creds: Optional[Credentials] = None

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.debug("Refreshing expired OAuth token")
                creds.refresh(Request())
            else:
                logger.debug("Running OAuth authorization flow")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(cred_path), _SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Persist the token for next run
            token_path.write_text(creds.to_json(), encoding="utf-8")
            logger.info("OAuth token saved to %s", token_path)

        return creds

    def _event_to_item(self, event: Dict) -> Dict:
        """Convert a raw Google Calendar event to a standardised item."""
        summary = event.get("summary", "(无标题)")
        description = event.get("description", "")
        location = event.get("location", "")
        html_link = event.get("htmlLink", "")

        # Extract start/end times – all-day events use "date", others use "dateTime"
        start = event.get("start", {})
        end = event.get("end", {})
        start_time = start.get("dateTime", start.get("date", ""))
        end_time = end.get("dateTime", end.get("date", ""))

        # Build content for LLM analysis
        content_parts = [f"事件: {summary}"]
        if description:
            content_parts.append(f"描述: {description}")
        if location:
            content_parts.append(f"地点: {location}")
        if start_time:
            content_parts.append(f"开始时间: {start_time}")
        if end_time:
            content_parts.append(f"结束时间: {end_time}")

        # Include attendee count (not names, to reduce sensitivity)
        attendees = event.get("attendees", [])
        if attendees:
            content_parts.append(f"参会人数: {len(attendees)}")

        content = "\n".join(content_parts)

        # Format timestamp
        timestamp = self._format_timestamp(start_time)

        return {
            "source_type": self.source_type,
            "title": summary,
            "content": content,
            "metadata": {
                "event_id": event.get("id", ""),
                "location": location,
                "html_link": html_link,
                "start_time": start_time,
                "end_time": end_time,
                "attendee_count": len(attendees),
                "status": event.get("status", ""),
            },
            "timestamp": timestamp,
        }

    @staticmethod
    def _format_timestamp(iso_str: str) -> str:
        """Convert an ISO 8601 timestamp to ``YYYY-MM-DD HH:MM``."""
        if not iso_str:
            return ""
        try:
            # Handle timezone-aware ISO strings
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return iso_str[:16] if len(iso_str) >= 16 else iso_str

"""Data source abstraction layer for weekly report agent.

Provides a unified interface for collecting work items from various sources
(Git, calendar, chat, tasks, emails, etc.) to feed into LLM analysis.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Standard item format
# ---------------------------------------------------------------------------
# Each data source's fetch() method must return items matching this schema:
#
# {
#     "source_type": str,      # e.g. "git", "calendar", "chat"
#     "title": str,            # Short title / summary
#     "content": str,          # Full text content for LLM analysis
#     "metadata": Dict,        # Source-specific metadata (commit hash, etc.)
#     "timestamp": str,        # "YYYY-MM-DD HH:MM"
# }


class DataSource(ABC):
    """Unified data source abstract base class.

    All data source implementations must inherit from this class and
    implement the abstract properties and methods.  Concrete sources are
    responsible for fetching raw data from their respective platforms and
    converting it into the standardised item format described above.
    """

    # ------------------------------------------------------------------
    # Abstract properties
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Short identifier for the data source type (e.g. ``"git"``).

        This value is stored in each item's ``source_type`` field and can
        be used for filtering or display routing.
        """
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for the data source (e.g. ``"Git提交记录"``)."""
        ...

    # ------------------------------------------------------------------
    # Abstract methods
    # ------------------------------------------------------------------

    @abstractmethod
    def fetch(self, days: int = 7, **kwargs) -> List[Dict]:
        """Fetch work items from the last *days* days.

        Parameters
        ----------
        days : int
            How many days of history to retrieve (default 7).
        **kwargs
            Source-specific extra parameters.

        Returns
        -------
        list[dict]
            A list of standardised item dicts.  See module docstring for
            the expected schema.
        """
        ...

    # ------------------------------------------------------------------
    # Optional overrides
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether this data source is currently usable.

        Override this method to perform runtime checks (e.g. verify that
        a Git repository exists or that an API token is configured).

        Returns
        -------
        bool
            ``True`` if the source can be used, ``False`` otherwise.
        """
        return True

    def get_sensitivity_warning(self) -> Optional[str]:
        """Return a sensitivity warning message, or ``None`` if no warning.

        Some data sources may contain personally identifiable information
        or secrets.  Implementations can override this method to warn the
        user before data is sent to the LLM.

        Returns
        -------
        str or None
            Warning text, or ``None`` when no warning applies.
        """
        return None

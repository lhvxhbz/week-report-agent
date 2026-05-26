"""Data source implementations for weekly report agent.

This package provides concrete :class:`DataSource` implementations that
collect work items from various platforms (Git, calendar, chat, tasks, etc.).

Usage::

    from core.sources import GitSource, GoogleCalendarSource

    source = GitSource("/path/to/repo")
    items = source.fetch(days=7)
"""

from core.sources.git_source import GitSource
from core.sources.feishu_chat_source import FeishuChatSource
from core.sources.dingtalk_source import DingTalkSource
from core.sources.wechat_work_source import WeChatWorkSource
from core.sources.email_source import EmailSource

# ------------------------------------------------------------------
# Future data sources (uncomment as they are implemented)
# ------------------------------------------------------------------
# from core.sources.google_calendar_source import GoogleCalendarSource
# from core.sources.jira_source import JiraSource
# from core.sources.notion_source import NotionSource

__all__ = [
    "GitSource",
    "FeishuChatSource",
    "DingTalkSource",
    "WeChatWorkSource",
    "EmailSource",
]

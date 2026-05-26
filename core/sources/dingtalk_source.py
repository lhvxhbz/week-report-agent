"""钉钉聊天记录数据源。

通过钉钉开放平台 API 获取聊天记录，支持获取指定天数内的消息。
需要配置钉钉应用的 App Key 和 App Secret。

注意事项：
- 获取聊天记录需要企业内部应用权限
- 需要申请智能工作群相关权限
- 聊天记录可能包含敏感信息，使用前请确认
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.data_source import DataSource

logger = logging.getLogger(__name__)


class DingTalkSource(DataSource):
    """钉钉聊天记录数据源。

    通过钉钉开放平台 API 获取聊天记录，支持获取指定天数内的消息。
    需要配置钉钉应用的 App Key 和 App Secret。

    Parameters
    ----------
    app_key : str
        钉钉应用的 App Key。
    app_secret : str
        钉钉应用的 App Secret。

    Examples
    --------
    >>> source = DingTalkSource("ding_xxx", "secret_xxx")
    >>> if source.is_available():
    ...     items = source.fetch(days=7)
    ...     for item in items:
    ...         print(item["title"])
    """

    source_type = "dingtalk"
    display_name = "钉钉聊天记录"

    def __init__(self, app_key: str, app_secret: str) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def _get_access_token(self) -> str:
        """获取或刷新 access_token。

        钉钉的 access_token 有效期为 7200 秒，会自动缓存和刷新。

        Returns
        -------
        str
            有效的 access_token。

        Raises
        ------
        ImportError
            如果 requests 未安装。
        RuntimeError
            如果获取令牌失败。
        """
        # 检查缓存的 token 是否仍然有效
        if (
            self._access_token
            and self._token_expires_at
            and datetime.now() < self._token_expires_at
        ):
            return self._access_token

        try:
            import requests
        except ImportError:
            raise ImportError(
                "请安装 requests: pip install requests"
            )

        url = "https://oapi.dingtalk.com/gettoken"
        params = {
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("errcode") != 0:
            raise RuntimeError(
                f"获取 access_token 失败: {data.get('errmsg', '未知错误')}"
            )

        self._access_token = data.get("access_token")
        # 提前 5 分钟刷新
        expires_in = data.get("expires_in", 7200) - 300
        self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

        return self._access_token

    def fetch(self, days: int = 7, **kwargs) -> List[Dict]:
        """获取钉钉聊天记录。

        Parameters
        ----------
        days : int
            获取最近多少天的聊天记录，默认 7 天。
        **kwargs
            额外参数：
            - chat_id : str, optional
                指定群聊 ID。如果不指定，获取所有群聊的消息。
            - max_results : int, optional
                每次请求返回的最大消息数量，默认 100。

        Returns
        -------
        list[dict]
            标准化的聊天记录列表。每个字典包含：
            - source_type: "dingtalk"
            - title: 消息摘要
            - content: 消息内容
            - metadata: 包含 chat_id, sender_id, msg_id 等
            - timestamp: 消息发送时间

        Raises
        ------
        RuntimeError
            如果 API 调用失败。
        """
        try:
            import requests
        except ImportError:
            raise ImportError(
                "请安装 requests: pip install requests"
            )

        access_token = self._get_access_token()
        chat_id = kwargs.get("chat_id")
        max_results = kwargs.get("max_results", 100)

        # 计算时间范围
        start_time = datetime.now() - timedelta(days=days)
        start_timestamp = int(start_time.timestamp() * 1000)

        items: List[Dict] = []

        # 如果指定了 chat_id，直接获取该群聊的消息
        if chat_id:
            items.extend(
                self._fetch_group_messages(
                    access_token, chat_id, start_timestamp, max_results
                )
            )
        else:
            # 获取所有群聊
            groups = self._list_groups(access_token)
            for group in groups:
                group_id = group.get("openConversationId")
                if group_id:
                    items.extend(
                        self._fetch_group_messages(
                            access_token,
                            group_id,
                            start_timestamp,
                            max_results,
                        )
                    )

        return items

    def _list_groups(self, access_token: str) -> List[Dict]:
        """获取机器人所在的群聊列表。

        Parameters
        ----------
        access_token : str
            钉钉 access_token。

        Returns
        -------
        list[dict]
            群聊列表，每个字典包含 openConversationId, name 等信息。
        """
        try:
            import requests
        except ImportError:
            raise ImportError(
                "请安装 requests: pip install requests"
            )

        url = "https://oapi.dingtalk.com/chat/scencegroups"
        params = {"access_token": access_token}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("errcode") != 0:
            logger.warning(
                "获取群聊列表失败: %s", data.get("errmsg", "未知错误")
            )
            return []

        groups = data.get("result", {}).get("openConversationList", [])
        return [
            {
                "openConversationId": g.get("openConversationId"),
                "name": g.get("title", ""),
            }
            for g in groups
        ]

    def _fetch_group_messages(
        self,
        access_token: str,
        chat_id: str,
        start_time: int,
        max_results: int,
    ) -> List[Dict]:
        """获取指定群聊的消息列表。

        Parameters
        ----------
        access_token : str
            钉钉 access_token。
        chat_id : str
            群聊 ID。
        start_time : int
            起始时间戳（毫秒）。
        max_results : int
            每次请求返回的最大消息数量。

        Returns
        -------
        list[dict]
            标准化的消息列表。
        """
        try:
            import requests
        except ImportError:
            raise ImportError(
                "请安装 requests: pip install requests"
            )

        items: List[Dict] = []
        next_token = None

        while True:
            url = "https://oapi.dingtalk.com/topapi/message/listbyquery"
            params = {"access_token": access_token}
            payload = {
                "openConversationId": chat_id,
                "startTime": start_time,
                "endTime": int(datetime.now().timestamp() * 1000),
                "maxResults": max_results,
            }

            if next_token:
                payload["nextToken"] = next_token

            response = requests.post(
                url, params=params, json=payload, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get("errcode") != 0:
                logger.warning(
                    "获取群聊 %s 的消息失败: %s",
                    chat_id,
                    data.get("errmsg", "未知错误"),
                )
                break

            result = data.get("result", {})
            messages = result.get("messageList", [])

            for message in messages:
                item = self._parse_message(message, chat_id)
                if item:
                    items.append(item)

            # 检查是否有下一页
            has_more = result.get("hasMore", False)
            next_token = result.get("nextToken")

            if not has_more or not next_token:
                break

        return items

    def _parse_message(self, message: Dict, chat_id: str) -> Optional[Dict]:
        """解析单条消息为标准格式。

        Parameters
        ----------
        message : dict
            钉钉消息字典。
        chat_id : str
            群聊 ID。

        Returns
        -------
        dict or None
            标准化的消息字典，如果消息无法解析则返回 None。
        """
        try:
            import json

            # 解析消息内容
            content_str = message.get("content", "{}")
            try:
                content_json = json.loads(content_str) if isinstance(content_str, str) else content_str
            except json.JSONDecodeError:
                content_json = {}

            # 根据消息类型提取文本
            msg_type = message.get("msgtype", "text")
            text_content = ""

            if msg_type == "text":
                text_content = content_json.get("content", "")
            elif msg_type == "markdown":
                text_content = content_json.get("text", "")
                title = content_json.get("title", "")
                if title:
                    text_content = f"{title}\n{text_content}"
            elif msg_type == "richText":
                # 富文本消息
                rich_text = content_json.get("richText", {})
                paragraphs = []
                for item in rich_text.get("paragraphs", []):
                    for elem in item:
                        if elem.get("type") == "text":
                            paragraphs.append(elem.get("text", ""))
                text_content = "\n".join(paragraphs)
            elif msg_type == "actionCard":
                # 卡片消息
                text_content = content_json.get("title", "")
                markdown = content_json.get("markdown", "")
                if markdown:
                    text_content = f"{text_content}\n{markdown}"
            else:
                text_content = f"[{msg_type} 消息]"

            if not text_content:
                return None

            # 生成消息摘要
            title = text_content[:50] + ("..." if len(text_content) > 50 else "")

            # 解析时间戳
            create_time = message.get("createAt", 0)
            try:
                timestamp = datetime.fromtimestamp(
                    create_time / 1000
                ).strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

            return {
                "source_type": self.source_type,
                "title": title,
                "content": text_content,
                "metadata": {
                    "chat_id": chat_id,
                    "msg_id": message.get("msgId"),
                    "sender_id": message.get("senderId"),
                    "msg_type": msg_type,
                    "chat_name": message.get("chatName"),
                },
                "timestamp": timestamp,
            }
        except Exception as e:
            logger.warning("解析消息失败: %s", str(e))
            return None

    def is_available(self) -> bool:
        """检查钉钉配置是否完整。

        Returns
        -------
        bool
            如果 App Key 和 App Secret 均已配置则返回 True。
        """
        return bool(self.app_key and self.app_secret)

    def get_sensitivity_warning(self) -> Optional[str]:
        """返回敏感信息警告。

        Returns
        -------
        str or None
            警告信息文本。
        """
        return (
            "聊天记录可能包含敏感信息（如密码、个人信息等），"
            "请确认是否继续导入？"
        )

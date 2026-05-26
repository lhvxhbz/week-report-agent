"""企业微信聊天记录数据源。

通过企业微信 API 获取聊天记录，支持获取指定天数内的消息。
需要配置企业微信的 Corp ID 和 Corp Secret。

注意事项：
- 获取聊天记录需要企业管理员权限
- 需要开启会话内容存档功能
- 聊天记录可能包含敏感信息，使用前请确认
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.data_source import DataSource

logger = logging.getLogger(__name__)


class WeChatWorkSource(DataSource):
    """企业微信聊天记录数据源。

    通过企业微信 API 获取聊天记录，支持获取指定天数内的消息。
    需要配置企业微信的 Corp ID 和 Corp Secret。

    Parameters
    ----------
    corp_id : str
        企业微信的 Corp ID。
    corp_secret : str
        企业微信的 Corp Secret。
    agent_id : str, optional
        应用的 Agent ID，用于获取应用消息。

    Examples
    --------
    >>> source = WeChatWorkSource("ww_xxx", "secret_xxx")
    >>> if source.is_available():
    ...     items = source.fetch(days=7)
    ...     for item in items:
    ...         print(item["title"])
    """

    source_type = "wechat_work"
    display_name = "企业微信聊天记录"

    def __init__(
        self,
        corp_id: str,
        corp_secret: str,
        agent_id: Optional[str] = None,
    ) -> None:
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.agent_id = agent_id
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def _get_access_token(self) -> str:
        """获取或刷新 access_token。

        企业微信的 access_token 有效期为 7200 秒，会自动缓存和刷新。

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

        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {
            "corpid": self.corp_id,
            "corpsecret": self.corp_secret,
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
        """获取企业微信聊天记录。

        Parameters
        ----------
        days : int
            获取最近多少天的聊天记录，默认 7 天。
        **kwargs
            额外参数：
            - room_id : str, optional
                指定群聊 ID。如果不指定，获取所有群聊的消息。
            - limit : int, optional
                每次请求返回的最大消息数量，默认 100。

        Returns
        -------
        list[dict]
            标准化的聊天记录列表。每个字典包含：
            - source_type: "wechat_work"
            - title: 消息摘要
            - content: 消息内容
            - metadata: 包含 room_id, sender, msg_id 等
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
        room_id = kwargs.get("room_id")
        limit = kwargs.get("limit", 100)

        # 计算时间范围
        start_time = datetime.now() - timedelta(days=days)
        start_timestamp = int(start_time.timestamp())

        items: List[Dict] = []

        # 获取应用消息
        if self.agent_id:
            items.extend(
                self._fetch_app_messages(
                    access_token, start_timestamp, limit
                )
            )

        # 获取群聊消息（需要会话内容存档功能）
        if room_id:
            items.extend(
                self._fetch_group_messages(
                    access_token, room_id, start_timestamp, limit
                )
            )
        else:
            # 获取所有群聊
            groups = self._list_groups(access_token)
            for group in groups:
                chat_id = group.get("chat_id")
                if chat_id:
                    items.extend(
                        self._fetch_group_messages(
                            access_token, chat_id, start_timestamp, limit
                        )
                    )

        return items

    def _fetch_app_messages(
        self,
        access_token: str,
        start_time: int,
        limit: int,
    ) -> List[Dict]:
        """获取应用消息列表。

        Parameters
        ----------
        access_token : str
            企业微信 access_token。
        start_time : int
            起始时间戳（秒）。
        limit : int
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
        next_cursor = None

        while True:
            url = (
                f"https://qyapi.weixin.qq.com/cgi-bin/message/list"
                f"?access_token={access_token}"
            )
            payload = {
                "chat_type": "single",
                "start_time": start_time,
                "end_time": int(datetime.now().timestamp()),
                "limit": limit,
            }

            if next_cursor:
                payload["cursor"] = next_cursor

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("errcode") != 0:
                logger.warning(
                    "获取应用消息失败: %s", data.get("errmsg", "未知错误")
                )
                break

            messages = data.get("msg_list", [])
            for message in messages:
                item = self._parse_message(message)
                if item:
                    items.append(item)

            # 检查是否有下一页
            next_cursor = data.get("next_cursor")
            if not next_cursor:
                break

        return items

    def _list_groups(self, access_token: str) -> List[Dict]:
        """获取应用可见的群聊列表。

        Parameters
        ----------
        access_token : str
            企业微信 access_token。

        Returns
        -------
        list[dict]
            群聊列表，每个字典包含 chat_id, name 等信息。
        """
        try:
            import requests
        except ImportError:
            raise ImportError(
                "请安装 requests: pip install requests"
            )

        url = (
            f"https://qyapi.weixin.qq.com/cgi-bin/appchat/list"
            f"?access_token={access_token}"
        )
        params = {"limit": 100, "offset": 0}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("errcode") != 0:
            logger.warning(
                "获取群聊列表失败: %s", data.get("errmsg", "未知错误")
            )
            return []

        groups = data.get("chat_list", [])
        return [
            {
                "chat_id": g.get("chatid"),
                "name": g.get("name", ""),
            }
            for g in groups
        ]

    def _fetch_group_messages(
        self,
        access_token: str,
        room_id: str,
        start_time: int,
        limit: int,
    ) -> List[Dict]:
        """获取指定群聊的消息列表。

        注意：此功能需要开启会话内容存档功能，且需要企业管理员权限。

        Parameters
        ----------
        access_token : str
            企业微信 access_token。
        room_id : str
            群聊 ID。
        start_time : int
            起始时间戳（秒）。
        limit : int
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
        next_cursor = None

        while True:
            url = (
                f"https://qyapi.weixin.qq.com/cgi-bin/message/list"
                f"?access_token={access_token}"
            )
            payload = {
                "chat_type": "group",
                "room_id": room_id,
                "start_time": start_time,
                "end_time": int(datetime.now().timestamp()),
                "limit": limit,
            }

            if next_cursor:
                payload["cursor"] = next_cursor

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("errcode") != 0:
                logger.warning(
                    "获取群聊 %s 的消息失败: %s",
                    room_id,
                    data.get("errmsg", "未知错误"),
                )
                break

            messages = data.get("msg_list", [])
            for message in messages:
                item = self._parse_message(message, room_id)
                if item:
                    items.append(item)

            # 检查是否有下一页
            next_cursor = data.get("next_cursor")
            if not next_cursor:
                break

        return items

    def _parse_message(
        self, message: Dict, room_id: Optional[str] = None
    ) -> Optional[Dict]:
        """解析单条消息为标准格式。

        Parameters
        ----------
        message : dict
            企业微信消息字典。
        room_id : str, optional
            群聊 ID。

        Returns
        -------
        dict or None
            标准化的消息字典，如果消息无法解析则返回 None。
        """
        try:
            # 解析消息内容
            msg_type = message.get("msgtype", "text")
            text_content = ""

            if msg_type == "text":
                text_content = message.get("text", {}).get("content", "")
            elif msg_type == "markdown":
                text_content = message.get("markdown", {}).get("content", "")
            elif msg_type == "image":
                text_content = "[图片消息]"
            elif msg_type == "voice":
                text_content = "[语音消息]"
            elif msg_type == "video":
                text_content = "[视频消息]"
            elif msg_type == "file":
                file_name = message.get("file", {}).get("name", "未知文件")
                text_content = f"[文件: {file_name}]"
            elif msg_type == "link":
                link = message.get("link", {})
                title = link.get("title", "")
                desc = link.get("desc", "")
                text_content = f"{title}\n{desc}" if desc else title
            elif msg_type == "miniprogram":
                text_content = "[小程序消息]"
            else:
                text_content = f"[{msg_type} 消息]"

            if not text_content:
                return None

            # 生成消息摘要
            title = text_content[:50] + ("..." if len(text_content) > 50 else "")

            # 解析时间戳
            msg_time = message.get("msgtime", 0)
            try:
                timestamp = datetime.fromtimestamp(
                    int(msg_time)
                ).strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

            return {
                "source_type": self.source_type,
                "title": title,
                "content": text_content,
                "metadata": {
                    "room_id": room_id or message.get("room_id"),
                    "msg_id": message.get("msgid"),
                    "sender": message.get("from", {}).get("userid"),
                    "msg_type": msg_type,
                    "room_name": message.get("room_name"),
                },
                "timestamp": timestamp,
            }
        except Exception as e:
            logger.warning("解析消息失败: %s", str(e))
            return None

    def is_available(self) -> bool:
        """检查企业微信配置是否完整。

        Returns
        -------
        bool
            如果 Corp ID 和 Corp Secret 均已配置则返回 True。
        """
        return bool(self.corp_id and self.corp_secret)

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

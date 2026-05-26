"""飞书聊天记录数据源。

通过飞书开放平台 API 获取聊天记录，支持获取指定天数内的消息。
需要配置飞书应用的 App ID 和 App Secret。

注意事项：
- 获取聊天记录需要用户授权（user_access_token）
- 需要申请 im:message 和 im:chat 权限
- 聊天记录可能包含敏感信息，使用前请确认
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.data_source import DataSource

logger = logging.getLogger(__name__)


class FeishuChatSource(DataSource):
    """飞书聊天记录数据源。

    通过飞书开放平台 API 获取聊天记录，支持获取指定天数内的消息。
    需要配置飞书应用的 App ID 和 App Secret。

    Parameters
    ----------
    app_id : str
        飞书应用的 App ID。
    app_secret : str
        飞书应用的 App Secret。
    user_access_token : str, optional
        用户访问令牌，用于获取聊天记录。如果未提供，需要调用 authorize() 获取。

    Examples
    --------
    >>> source = FeishuChatSource("cli_xxx", "secret_xxx")
    >>> if source.is_available():
    ...     items = source.fetch(days=7)
    ...     for item in items:
    ...         print(item["title"])
    """

    source_type = "feishu_chat"
    display_name = "飞书聊天记录"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        user_access_token: Optional[str] = None,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.user_access_token = user_access_token
        self._client = None

    def _get_client(self):
        """获取或创建飞书 API 客户端。

        Returns
        -------
        lark.Client
            飞书 API 客户端实例。

        Raises
        ------
        ImportError
            如果 lark-oapi 未安装。
        """
        if self._client is not None:
            return self._client

        try:
            import lark_oapi as lark
        except ImportError:
            raise ImportError(
                "请安装 lark-oapi: pip install lark-oapi"
            )

        self._client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(lark.LogLevel.WARNING) \
            .build()

        return self._client

    def _get_tenant_access_token(self) -> str:
        """获取 tenant_access_token。

        Returns
        -------
        str
            租户访问令牌。

        Raises
        ------
        RuntimeError
            如果获取令牌失败。
        """
        try:
            import lark_oapi as lark
            from lark_oapi.api.auth.v3 import (
                InternalTenantAccessTokenRequest,
                InternalTenantAccessTokenRequestBody,
            )
        except ImportError:
            raise ImportError(
                "请安装 lark-oapi: pip install lark-oapi"
            )

        client = self._get_client()
        request = InternalTenantAccessTokenRequest.builder() \
            .request_body(
                InternalTenantAccessTokenRequestBody.builder()
                .app_id(self.app_id)
                .app_secret(self.app_secret)
                .build()
            ) \
            .build()

        response = client.auth.v3.tenant_access_token.internal(request)
        if not response.success():
            raise RuntimeError(
                f"获取 tenant_access_token 失败: {response.msg}"
            )

        return response.tenant_access_token

    def fetch(self, days: int = 7, **kwargs) -> List[Dict]:
        """获取飞书聊天记录。

        Parameters
        ----------
        days : int
            获取最近多少天的聊天记录，默认 7 天。
        **kwargs
            额外参数：
            - chat_id : str, optional
                指定聊天会话 ID。如果不指定，获取所有会话的消息。
            - page_size : int, optional
                每页返回的消息数量，默认 50。

        Returns
        -------
        list[dict]
            标准化的聊天记录列表。每个字典包含：
            - source_type: "feishu_chat"
            - title: 消息摘要
            - content: 消息内容
            - metadata: 包含 chat_id, sender_id, message_id 等
            - timestamp: 消息发送时间

        Raises
        ------
        RuntimeError
            如果 API 调用失败。
        """
        try:
            import lark_oapi as lark
            from lark_oapi.api.im.v1 import (
                ListMessageRequest,
            )
        except ImportError:
            raise ImportError(
                "请安装 lark-oapi: pip install lark-oapi"
            )

        client = self._get_client()
        chat_id = kwargs.get("chat_id")
        page_size = kwargs.get("page_size", 50)

        # 计算时间范围
        start_time = datetime.now() - timedelta(days=days)
        start_timestamp = str(int(start_time.timestamp()))

        items: List[Dict] = []

        # 如果指定了 chat_id，直接获取该会话的消息
        if chat_id:
            items.extend(
                self._fetch_chat_messages(
                    client, chat_id, start_timestamp, page_size
                )
            )
        else:
            # 获取所有会话
            chats = self._list_chats(client)
            for chat in chats:
                chat_id = chat.get("chat_id")
                if chat_id:
                    items.extend(
                        self._fetch_chat_messages(
                            client, chat_id, start_timestamp, page_size
                        )
                    )

        return items

    def _list_chats(self, client) -> List[Dict]:
        """获取机器人所在的会话列表。

        Parameters
        ----------
        client : lark.Client
            飞书 API 客户端。

        Returns
        -------
        list[dict]
            会话列表，每个字典包含 chat_id, name 等信息。
        """
        try:
            from lark_oapi.api.im.v1 import ListChatRequest
        except ImportError:
            raise ImportError(
                "请安装 lark-oapi: pip install lark-oapi"
            )

        request = ListChatRequest.builder() \
            .page_size(100) \
            .build()

        response = client.im.v1.chat.list(request)
        if not response.success():
            logger.warning(
                "获取会话列表失败: %s", response.msg
            )
            return []

        chats = []
        if response.data and response.data.items:
            for chat in response.data.items:
                chats.append({
                    "chat_id": chat.chat_id,
                    "name": chat.name,
                })

        return chats

    def _fetch_chat_messages(
        self,
        client,
        chat_id: str,
        start_time: str,
        page_size: int,
    ) -> List[Dict]:
        """获取指定会话的消息列表。

        Parameters
        ----------
        client : lark.Client
            飞书 API 客户端。
        chat_id : str
            会话 ID。
        start_time : str
            起始时间戳（秒）。
        page_size : int
            每页返回的消息数量。

        Returns
        -------
        list[dict]
            标准化的消息列表。
        """
        try:
            from lark_oapi.api.im.v1 import ListMessageRequest
        except ImportError:
            raise ImportError(
                "请安装 lark-oapi: pip install lark-oapi"
            )

        items: List[Dict] = []
        page_token = None

        while True:
            builder = ListMessageRequest.builder() \
                .container_id_type("chat") \
                .container_id(chat_id) \
                .start_time(start_time) \
                .page_size(page_size)

            if page_token:
                builder = builder.page_token(page_token)

            request = builder.build()
            response = client.im.v1.message.list(request)

            if not response.success():
                logger.warning(
                    "获取会话 %s 的消息失败: %s",
                    chat_id,
                    response.msg,
                )
                break

            if response.data and response.data.items:
                for message in response.data.items:
                    item = self._parse_message(message, chat_id)
                    if item:
                        items.append(item)

            # 检查是否有下一页
            if (
                response.data
                and response.data.has_more
                and response.data.page_token
            ):
                page_token = response.data.page_token
            else:
                break

        return items

    def _parse_message(self, message, chat_id: str) -> Optional[Dict]:
        """解析单条消息为标准格式。

        Parameters
        ----------
        message : lark.Message
            飞书消息对象。
        chat_id : str
            会话 ID。

        Returns
        -------
        dict or None
            标准化的消息字典，如果消息无法解析则返回 None。
        """
        try:
            import json

            # 解析消息内容
            content_str = message.body.content if message.body else "{}"
            try:
                content_json = json.loads(content_str)
            except json.JSONDecodeError:
                content_json = {}

            # 根据消息类型提取文本
            msg_type = message.msg_type or "text"
            text_content = ""

            if msg_type == "text":
                text_content = content_json.get("text", "")
            elif msg_type == "post":
                # 富文本消息，提取所有文本段落
                title = content_json.get("title", "")
                paragraphs = []
                for lang_content in content_json.values():
                    if isinstance(lang_content, list):
                        for paragraph in lang_content:
                            if isinstance(paragraph, list):
                                for elem in paragraph:
                                    if elem.get("tag") == "text":
                                        paragraphs.append(
                                            elem.get("text", "")
                                        )
                text_content = f"{title}\n{''.join(paragraphs)}".strip()
            elif msg_type == "interactive":
                # 卡片消息，提取标题和内容
                card_title = content_json.get("header", {}).get("title", {})
                if isinstance(card_title, dict):
                    text_content = card_title.get("content", "")
                else:
                    text_content = str(card_title)
            else:
                text_content = f"[{msg_type} 消息]"

            if not text_content:
                return None

            # 生成消息摘要
            title = text_content[:50] + ("..." if len(text_content) > 50 else "")

            # 解析时间戳
            create_time = message.create_time or "0"
            try:
                timestamp = datetime.fromtimestamp(
                    int(create_time) / 1000
                ).strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

            return {
                "source_type": self.source_type,
                "title": title,
                "content": text_content,
                "metadata": {
                    "chat_id": chat_id,
                    "message_id": message.message_id,
                    "sender_id": (
                        message.sender.id
                        if message.sender
                        else None
                    ),
                    "msg_type": msg_type,
                    "chat_name": getattr(message, "chat_name", None),
                },
                "timestamp": timestamp,
            }
        except Exception as e:
            logger.warning("解析消息失败: %s", str(e))
            return None

    def is_available(self) -> bool:
        """检查飞书配置是否完整。

        Returns
        -------
        bool
            如果 App ID 和 App Secret 均已配置则返回 True。
        """
        return bool(self.app_id and self.app_secret)

    def get_sensitivity_warning(self) -> str:
        """返回敏感信息警告。

        Returns
        -------
        str
            警告信息文本。
        """
        return (
            "聊天记录可能包含敏感信息（如密码、个人信息等），"
            "请确认是否继续导入？"
        )

"""邮件数据源。

通过 IMAP 协议获取邮件内容，支持获取指定天数内的邮件。
需要配置 IMAP 服务器地址、邮箱账号和密码。

注意事项：
- 邮件内容可能包含敏感信息（如密码、个人信息等）
- 支持 SSL/TLS 加密连接
- 支持解码各种编码格式的邮件头和正文
"""

import email
import imaplib
import logging
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

from core.data_source import DataSource

logger = logging.getLogger(__name__)


class EmailSource(DataSource):
    """邮件数据源。

    通过 IMAP 协议获取邮件内容，支持获取指定天数内的邮件。
    需要配置 IMAP 服务器地址、邮箱账号和密码。

    Parameters
    ----------
    imap_server : str
        IMAP 服务器地址（如 "imap.gmail.com"）。
    email : str
        邮箱账号。
    password : str
        邮箱密码或应用专用密码。
    port : int, optional
        IMAP 服务器端口，默认 993（SSL）。
    use_ssl : bool, optional
        是否使用 SSL 加密连接，默认 True。

    Examples
    --------
    >>> source = EmailSource("imap.gmail.com", "user@gmail.com", "password")
    >>> if source.is_available():
    ...     items = source.fetch(days=7)
    ...     for item in items:
    ...         print(item["title"])
    """

    source_type = "email"
    display_name = "邮件"

    def __init__(
        self,
        imap_server: str,
        email: str,
        password: str,
        port: int = 993,
        use_ssl: bool = True,
    ) -> None:
        self.imap_server = imap_server
        self.email = email
        self.password = password
        self.port = port
        self.use_ssl = use_ssl

    def _connect(self) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        """建立 IMAP 连接。

        Returns
        -------
        imaplib.IMAP4_SSL or imaplib.IMAP4
            IMAP 连接对象。

        Raises
        ------
        ConnectionError
            如果连接失败。
        """
        try:
            if self.use_ssl:
                mail = imaplib.IMAP4_SSL(self.imap_server, self.port)
            else:
                mail = imaplib.IMAP4(self.imap_server, self.port)

            mail.login(self.email, self.password)
            return mail
        except imaplib.IMAP4.error as e:
            raise ConnectionError(f"IMAP 登录失败: {str(e)}")
        except Exception as e:
            raise ConnectionError(f"连接 IMAP 服务器失败: {str(e)}")

    def fetch(self, days: int = 7, **kwargs) -> List[Dict]:
        """获取最近 N 天的邮件。

        Parameters
        ----------
        days : int
            获取最近多少天的邮件，默认 7 天。
        **kwargs
            额外参数：
            - folder : str, optional
                邮箱文件夹，默认 "INBOX"。
            - limit : int, optional
                最大返回邮件数量，默认 100。
            - search_criteria : str, optional
                自定义 IMAP 搜索条件，覆盖默认的日期搜索。

        Returns
        -------
        list[dict]
            标准化的邮件列表。每个字典包含：
            - source_type: "email"
            - title: 邮件主题
            - content: 邮件正文
            - metadata: 包含 from, to, cc, attachments 等
            - timestamp: 邮件发送时间

        Raises
        ------
        ConnectionError
            如果无法连接到 IMAP 服务器。
        """
        folder = kwargs.get("folder", "INBOX")
        limit = kwargs.get("limit", 100)
        search_criteria = kwargs.get("search_criteria")

        # 计算日期范围
        since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

        # 默认搜索条件：最近 N 天的邮件
        if not search_criteria:
            search_criteria = f'(SINCE "{since_date}")'

        items: List[Dict] = []
        mail = None

        try:
            mail = self._connect()
            mail.select(folder, readonly=True)

            # 搜索邮件
            status, message_ids = mail.search(None, search_criteria)
            if status != "OK":
                logger.warning("搜索邮件失败: %s", status)
                return []

            # 获取邮件 ID 列表
            id_list = message_ids[0].split()
            # 限制返回数量（取最新的）
            id_list = id_list[-limit:] if len(id_list) > limit else id_list

            for msg_id in id_list:
                try:
                    item = self._fetch_single_email(mail, msg_id)
                    if item:
                        items.append(item)
                except Exception as e:
                    logger.warning(
                        "获取邮件 %s 失败: %s", msg_id.decode(), str(e)
                    )
                    continue

        finally:
            if mail:
                try:
                    mail.logout()
                except Exception:
                    pass

        return items

    def _fetch_single_email(
        self, mail: imaplib.IMAP4_SSL | imaplib.IMAP4, msg_id: bytes
    ) -> Optional[Dict]:
        """获取单封邮件的详细内容。

        Parameters
        ----------
        mail : imaplib.IMAP4_SSL or imaplib.IMAP4
            IMAP 连接对象。
        msg_id : bytes
            邮件 ID。

        Returns
        -------
        dict or None
            标准化的邮件字典，如果邮件无法解析则返回 None。
        """
        status, msg_data = mail.fetch(msg_id, "(RFC822)")
        if status != "OK":
            return None

        # 解析邮件
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # 提取邮件头信息
        subject = self._decode_header(msg.get("Subject", ""))
        from_addr = self._decode_header(msg.get("From", ""))
        to_addr = self._decode_header(msg.get("To", ""))
        cc_addr = self._decode_header(msg.get("Cc", ""))
        date_str = msg.get("Date", "")

        # 解析发送时间
        try:
            if date_str:
                date_obj = parsedate_to_datetime(date_str)
                timestamp = date_obj.strftime("%Y-%m-%d %H:%M")
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 提取邮件正文
        body = self._extract_body(msg)

        # 提取附件信息
        attachments = self._extract_attachments(msg)

        if not subject and not body:
            return None

        # 生成内容（包含主题和正文）
        content = f"主题: {subject}\n"
        content += f"发件人: {from_addr}\n"
        content += f"收件人: {to_addr}\n"
        if cc_addr:
            content += f"抄送: {cc_addr}\n"
        content += f"\n{body}"

        # 生成摘要
        title = subject or body[:50] + ("..." if len(body) > 50 else "")

        return {
            "source_type": self.source_type,
            "title": title,
            "content": content,
            "metadata": {
                "from": from_addr,
                "to": to_addr,
                "cc": cc_addr,
                "subject": subject,
                "attachments": attachments,
                "message_id": msg.get("Message-ID"),
            },
            "timestamp": timestamp,
        }

    def _decode_header(self, header: str) -> str:
        """解码邮件头信息。

        Parameters
        ----------
        header : str
            编码后的邮件头信息。

        Returns
        -------
        str
            解码后的字符串。
        """
        if not header:
            return ""

        try:
            decoded_parts = decode_header(header)
            result = []
            for part, charset in decoded_parts:
                if isinstance(part, bytes):
                    charset = charset or "utf-8"
                    try:
                        result.append(part.decode(charset, errors="replace"))
                    except (LookupError, UnicodeDecodeError):
                        result.append(part.decode("utf-8", errors="replace"))
                else:
                    result.append(str(part))
            return " ".join(result)
        except Exception as e:
            logger.warning("解码邮件头失败: %s", str(e))
            return str(header)

    def _extract_body(self, msg: email.message.Message) -> str:
        """提取邮件正文。

        Parameters
        ----------
        msg : email.message.Message
            邮件消息对象。

        Returns
        -------
        str
            邮件正文内容。
        """
        body = ""

        if msg.is_multipart():
            # 多部分邮件，优先获取纯文本内容
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # 跳过附件
                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            body = payload.decode(charset, errors="replace")
                        except (LookupError, UnicodeDecodeError):
                            body = payload.decode("utf-8", errors="replace")
                        break
                elif content_type == "text/html" and not body:
                    # 如果没有纯文本，尝试从 HTML 提取
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            html_content = payload.decode(charset, errors="replace")
                        except (LookupError, UnicodeDecodeError):
                            html_content = payload.decode("utf-8", errors="replace")
                        # 简单的 HTML 转文本
                        body = self._html_to_text(html_content)
        else:
            # 单部分邮件
            content_type = msg.get_content_type()
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                try:
                    content = payload.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    content = payload.decode("utf-8", errors="replace")

                if content_type == "text/html":
                    body = self._html_to_text(content)
                else:
                    body = content

        return body.strip()

    def _html_to_text(self, html: str) -> str:
        """简单的 HTML 转文本转换。

        Parameters
        ----------
        html : str
            HTML 内容。

        Returns
        -------
        str
            转换后的纯文本。
        """
        try:
            # 尝试使用 BeautifulSoup
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            # 移除 script 和 style 标签
            for tag in soup(["script", "style"]):
                tag.decompose()
            return soup.get_text(separator="\n", strip=True)
        except ImportError:
            # 如果没有 BeautifulSoup，使用简单的正则替换
            import re
            # 移除 HTML 标签
            text = re.sub(r"<[^>]+>", " ", html)
            # 移除多余空白
            text = re.sub(r"\s+", " ", text)
            # 解码常见的 HTML 实体
            text = text.replace("&amp;", "&")
            text = text.replace("&lt;", "<")
            text = text.replace("&gt;", ">")
            text = text.replace("&nbsp;", " ")
            text = text.replace("&quot;", '"')
            return text.strip()

    def _extract_attachments(self, msg: email.message.Message) -> List[Dict]:
        """提取附件信息。

        Parameters
        ----------
        msg : email.message.Message
            邮件消息对象。

        Returns
        -------
        list[dict]
            附件列表，每个字典包含 filename 和 content_type。
        """
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        filename = self._decode_header(filename)
                        attachments.append({
                            "filename": filename,
                            "content_type": part.get_content_type(),
                        })

        return attachments

    def is_available(self) -> bool:
        """检查邮件配置是否完整。

        Returns
        -------
        bool
            如果 IMAP 服务器、邮箱和密码均已配置则返回 True。
        """
        return bool(self.imap_server and self.email and self.password)

    def get_sensitivity_warning(self) -> str:
        """返回敏感信息警告。

        Returns
        -------
        str
            警告信息文本。
        """
        return (
            "邮件内容可能包含敏感信息（如密码、个人信息等），"
            "请确认是否继续导入？"
        )

"""周报历史归档模块。

提供周报的持久化存储、查询和管理功能。
每次生成周报后自动归档，支持按时间查看历史周报详情。
存储方式：本地 SQLite 数据库，可靠且便于查询。
"""

import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DB_DIR = Path(__file__).resolve().parent.parent / ".history"
_DB_PATH = _DB_DIR / "report_archive.db"

# 线程锁，保证并发写入安全
_db_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def _ensure_db() -> None:
    """确保数据库目录和表结构存在。"""
    _DB_DIR.mkdir(parents=True, exist_ok=True)

    with _db_lock:
        conn = sqlite3.connect(str(_DB_PATH))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS report_archive (
                    report_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    date_range TEXT NOT NULL DEFAULT '',
                    template_name TEXT NOT NULL DEFAULT '',
                    report_content TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    source_files_count INTEGER NOT NULL DEFAULT 0,
                    source_files_info TEXT NOT NULL DEFAULT '[]',
                    export_path TEXT NOT NULL DEFAULT '',
                    work_dir TEXT NOT NULL DEFAULT '',
                    scan_days INTEGER NOT NULL DEFAULT 7,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_report_archive_created_at
                ON report_archive (created_at DESC)
            """)
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _generate_report_id() -> str:
    """生成唯一的报告ID。格式：日期时间_短UUID。"""
    now = datetime.now()
    short_id = uuid.uuid4().hex[:8]
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{short_id}"


def _extract_summary(report_content: str, max_length: int = 100) -> str:
    """从周报内容中提取摘要。

    优先提取"工作总结"部分的内容，否则取前几行非空文本。

    Parameters
    ----------
    report_content : str
        完整的周报 Markdown 内容。
    max_length : int
        摘要最大字符数。

    Returns
    -------
    str
        摘要文本。
    """
    if not report_content:
        return ""

    lines = report_content.strip().split("\n")

    # 尝试提取"工作总结"部分
    in_summary_section = False
    summary_lines = []

    for line in lines:
        stripped = line.strip()

        # 检测"工作总结"标题
        if stripped.startswith("#") and "工作总结" in stripped:
            in_summary_section = True
            continue

        if in_summary_section:
            # 遇到下一个标题时停止
            if stripped.startswith("#"):
                break
            if stripped:
                summary_lines.append(stripped)

    if summary_lines:
        summary = " ".join(summary_lines)
        if len(summary) > max_length:
            return summary[:max_length] + "..."
        return summary

    # 备选：取第一个非标题、非空行
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
            if len(stripped) > max_length:
                return stripped[:max_length] + "..."
            return stripped

    return "（无摘要）"


def _extract_title(report_content: str) -> str:
    """从周报内容中提取标题（第一个 # 标题行）。

    Parameters
    ----------
    report_content : str
        完整的周报 Markdown 内容。

    Returns
    -------
    str
        标题文本，不含 # 前缀。
    """
    if not report_content:
        return ""

    for line in report_content.strip().split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()

    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def archive_report(
    report_content: str,
    date_range: str = "",
    template_name: str = "",
    source_files: Optional[List[Dict]] = None,
    work_dir: str = "",
    scan_days: int = 7,
    export_path: str = "",
    metadata: Optional[Dict] = None,
) -> str:
    """归档一份周报。

    Parameters
    ----------
    report_content : str
        完整的周报 Markdown 内容。
    date_range : str
        周报覆盖的日期范围（如 "05.22 - 05.28"）。
    template_name : str
        使用的模板名称。
    source_files : list[dict], optional
        来源文件列表，每个文件包含 name, path, relative 等信息。
    work_dir : str
        工作目录路径。
    scan_days : int
        扫描天数。
    export_path : str
        导出文件路径（如有）。
    metadata : dict, optional
        额外元数据。

    Returns
    -------
    str
        归档的 report_id，失败时返回空字符串。
    """
    _ensure_db()

    report_id = _generate_report_id()
    created_at = datetime.now().isoformat()
    summary = _extract_summary(report_content)

    # 构建来源文件信息
    source_files_count = 0
    source_files_info = "[]"
    if source_files:
        source_files_count = len(source_files)
        # 只保存必要的文件信息（名称、路径、大小）
        import json
        files_brief = [
            {
                "name": f.get("name", ""),
                "relative": f.get("relative", ""),
                "ext": f.get("ext", ""),
                "size": f.get("size", 0),
                "modified": f.get("modified", ""),
            }
            for f in source_files
        ]
        source_files_info = json.dumps(files_brief, ensure_ascii=False)

    # 序列化 metadata
    import json
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

    with _db_lock:
        try:
            conn = sqlite3.connect(str(_DB_PATH))
            conn.execute(
                """
                INSERT INTO report_archive (
                    report_id, created_at, date_range, template_name,
                    report_content, summary, source_files_count,
                    source_files_info, export_path, work_dir,
                    scan_days, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id, created_at, date_range, template_name,
                    report_content, summary, source_files_count,
                    source_files_info, export_path, work_dir,
                    scan_days, metadata_json,
                ),
            )
            conn.commit()
            conn.close()
            logger.info("周报已归档: %s", report_id)
            return report_id
        except Exception as e:
            logger.error("周报归档失败: %s", e)
            return ""


def list_archived_reports(
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """列出已归档的周报，按时间倒序排列。

    Parameters
    ----------
    limit : int
        返回的最大记录数（默认 50）。
    offset : int
        偏移量，用于分页。

    Returns
    -------
    list[dict]
        周报归档列表，每条包含：
        - report_id
        - created_at
        - date_range
        - template_name
        - summary
        - source_files_count
        - work_dir
        - scan_days
    """
    _ensure_db()

    with _db_lock:
        try:
            conn = sqlite3.connect(str(_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT report_id, created_at, date_range, template_name,
                       summary, source_files_count, work_dir, scan_days
                FROM report_archive
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("查询周报归档列表失败: %s", e)
            return []


def get_archived_report(report_id: str) -> Optional[Dict]:
    """获取单条周报归档的完整详情。

    Parameters
    ----------
    report_id : str
        周报归档 ID。

    Returns
    -------
    dict or None
        完整的周报归档数据，包含所有字段。
    """
    _ensure_db()

    with _db_lock:
        try:
            conn = sqlite3.connect(str(_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM report_archive WHERE report_id = ?
                """,
                (report_id,),
            )
            row = cursor.fetchone()
            conn.close()

            if row is None:
                return None

            result = dict(row)
            # 反序列化 JSON 字段
            import json
            try:
                result["source_files_info"] = json.loads(
                    result.get("source_files_info", "[]")
                )
            except (json.JSONDecodeError, TypeError):
                result["source_files_info"] = []
            try:
                result["metadata"] = json.loads(
                    result.get("metadata", "{}")
                )
            except (json.JSONDecodeError, TypeError):
                result["metadata"] = {}

            return result
        except Exception as e:
            logger.error("查询周报归档详情失败: %s", e)
            return None


def delete_archived_report(report_id: str) -> bool:
    """删除一条周报归档记录。

    Parameters
    ----------
    report_id : str
        周报归档 ID。

    Returns
    -------
    bool
        删除是否成功。
    """
    _ensure_db()

    with _db_lock:
        try:
            conn = sqlite3.connect(str(_DB_PATH))
            cursor = conn.execute(
                "DELETE FROM report_archive WHERE report_id = ?",
                (report_id,),
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            if deleted:
                logger.info("已删除周报归档: %s", report_id)
            return deleted
        except Exception as e:
            logger.error("删除周报归档失败: %s", e)
            return False


def get_archive_stats() -> Dict:
    """获取归档统计信息。

    Returns
    -------
    dict
        包含：
        - total_count: 总归档数
        - latest_time: 最近归档时间
        - oldest_time: 最早归档时间
    """
    _ensure_db()

    with _db_lock:
        try:
            conn = sqlite3.connect(str(_DB_PATH))
            cursor = conn.execute(
                "SELECT COUNT(*) as cnt, MIN(created_at) as oldest, MAX(created_at) as latest FROM report_archive"
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    "total_count": row[0],
                    "oldest_time": row[1],
                    "latest_time": row[2],
                }
            return {"total_count": 0, "oldest_time": None, "latest_time": None}
        except Exception as e:
            logger.error("查询归档统计失败: %s", e)
            return {"total_count": 0, "oldest_time": None, "latest_time": None}


def update_export_path(report_id: str, export_path: str) -> bool:
    """更新周报的导出路径。

    Parameters
    ----------
    report_id : str
        周报归档 ID。
    export_path : str
        导出文件路径。

    Returns
    -------
    bool
        更新是否成功。
    """
    _ensure_db()

    with _db_lock:
        try:
            conn = sqlite3.connect(str(_DB_PATH))
            cursor = conn.execute(
                "UPDATE report_archive SET export_path = ? WHERE report_id = ?",
                (export_path, report_id),
            )
            updated = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return updated
        except Exception as e:
            logger.error("更新导出路径失败: %s", e)
            return False

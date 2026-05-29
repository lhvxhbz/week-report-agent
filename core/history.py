"""历史记录存储模块，用于追踪文件变更和记录工作历史。

提供历史记录的保存、加载、比较和管理功能。
"""

import json
import logging
import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HISTORY_DIR = Path(__file__).resolve().parent.parent / ".history"
_SNAPSHOTS_FILE = _HISTORY_DIR / "snapshots.json"


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _ensure_dirs() -> None:
    """确保历史记录目录存在."""
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _get_file_hash(file_path: str) -> str:
    """根据文件路径和修改时间生成哈希值."""
    try:
        stat = os.stat(file_path)
        # 使用路径 + 修改时间 + 文件大小作为缓存键
        key = f"{file_path}:{stat.st_mtime}:{stat.st_size}"
        return hashlib.md5(key.encode()).hexdigest()
    except OSError:
        return hashlib.md5(file_path.encode()).hexdigest()


def _format_timestamp(timestamp: float) -> str:
    """格式化时间戳为可读字符串."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------

def save_snapshot(
    files: List[Dict],
    analyses: List[Dict],
    report: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> str:
    """保存一次扫描的快照。

    如果同一天已有快照，会自动删除之前的快照，只保留最后一次。
    快照保存时会自动清理超过保留天数的旧快照。

    Parameters
    ----------
    files : list[dict]
        文件列表，每个文件包含 path, name, modified, size, ext 等信息。
    analyses : list[dict]
        分析结果列表。
    report : str, optional
        生成的报告内容。
    metadata : dict, optional
        额外的元数据，可包含：
        - scan_days: 扫描天数
        - work_dir: 工作目录
        - scan_only: 是否仅为扫描（未生成报告）
        - retention_days: 快照保留天数（默认30）

    Returns
    -------
    str
        快照ID。
    """
    _ensure_dirs()

    now = datetime.now()
    snapshot_id = now.strftime("%Y%m%d_%H%M%S")
    timestamp = now.isoformat()
    today_str = now.strftime("%Y%m%d")

    # 获取保留天数（默认30天）
    retention_days = 30
    if metadata and "retention_days" in metadata:
        retention_days = metadata["retention_days"]

    # 构建文件快照（包含文件内容用于后续diff对比）
    file_snapshots = []
    for file_info in files:
        file_path = file_info.get("path", "")
        file_hash = _get_file_hash(file_path)
        # 读取文件内容用于后续增量对比
        file_content = ""
        try:
            from core.file_reader import read_file
            file_content = read_file(file_path)
            if file_content.startswith("[Error]") or file_content.startswith("[Skipped]"):
                file_content = ""
        except Exception:
            file_content = ""
        
        file_snapshots.append({
            "path": file_path,
            "name": file_info.get("name", ""),
            "relative": file_info.get("relative", ""),
            "hash": file_hash,
            "modified": file_info.get("modified", ""),
            "size": file_info.get("size", 0),
            "ext": file_info.get("ext", ""),
            "content": file_content,
        })

    # 构建分析结果快照
    analysis_snapshots = []
    for analysis in analyses:
        analysis_snapshots.append({
            "file_name": analysis.get("file_name", ""),
            "file_path": analysis.get("file_path", ""),
            "analysis": analysis.get("analysis", ""),
            "status": analysis.get("status", ""),
        })

    snapshot = {
        "id": snapshot_id,
        "timestamp": timestamp,
        "files": file_snapshots,
        "analyses": analysis_snapshots,
        "report": report,
        "metadata": metadata or {},
    }

    # 加载现有快照
    snapshots = _load_snapshots()

    # 删除同一天的旧快照（只保留最后一次）
    filtered_snapshots = []
    deleted_today = 0
    for s in snapshots:
        try:
            s_time = datetime.fromisoformat(s.get("timestamp", ""))
            s_date_str = s_time.strftime("%Y%m%d")
            if s_date_str == today_str:
                # 同一天的快照，删除
                deleted_today += 1
                continue
            filtered_snapshots.append(s)
        except (ValueError, TypeError):
            # 保留无法解析时间的快照
            filtered_snapshots.append(s)
    
    if deleted_today > 0:
        logger.info("删除了今天 %d 个旧快照", deleted_today)

    # 清理超过保留天数的旧快照
    cutoff = now - timedelta(days=retention_days)
    final_snapshots = []
    deleted_old = 0
    for s in filtered_snapshots:
        try:
            s_time = datetime.fromisoformat(s.get("timestamp", ""))
            if s_time >= cutoff:
                final_snapshots.append(s)
            else:
                deleted_old += 1
        except (ValueError, TypeError):
            # 保留无法解析时间的快照
            final_snapshots.append(s)
    
    if deleted_old > 0:
        logger.info("清理了 %d 个超过 %d 天的旧快照", deleted_old, retention_days)

    # 添加新快照
    final_snapshots.append(snapshot)

    # 保存快照
    try:
        _SNAPSHOTS_FILE.write_text(
            json.dumps(final_snapshots, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info("保存快照成功: %s", snapshot_id)
        return snapshot_id
    except Exception as e:
        logger.error("保存快照失败: %s", e)
        return ""


def _load_snapshots() -> List[Dict]:
    """加载所有快照."""
    if not _SNAPSHOTS_FILE.exists():
        return []

    try:
        data = _SNAPSHOTS_FILE.read_text(encoding="utf-8")
        return json.loads(data)
    except Exception as e:
        logger.error("加载快照失败: %s", e)
        return []


def get_latest_snapshot() -> Optional[Dict]:
    """获取最新的快照."""
    snapshots = _load_snapshots()
    if not snapshots:
        return None
    return snapshots[-1]


def get_snapshot_by_id(snapshot_id: str) -> Optional[Dict]:
    """根据ID获取快照."""
    snapshots = _load_snapshots()
    for snapshot in snapshots:
        if snapshot.get("id") == snapshot_id:
            return snapshot
    return None


def list_snapshots(limit: int = 10) -> List[Dict]:
    """列出最近的快照。"""
    snapshots = _load_snapshots()
    # 返回最近的limit个快照，按时间倒序
    return list(reversed(snapshots[-limit:]))


def compare_with_latest(files: List[Dict], scan_days: int = 7) -> Dict:
    """将当前文件列表与合适的快照进行比较。

    优先对比 scan_days 天前的快照，如果没有则往前推进找更早的快照。
    如果没有比 scan_days 更早的记录，则所有文件都当作新增。

    Parameters
    ----------
    files : list[dict]
        当前文件列表。
    scan_days : int
        当前扫描天数。

    Returns
    -------
    dict
        比较结果，包含：
        - added: 新增的文件
        - removed: 删除的文件
        - modified: 修改的文件
        - unchanged: 未变化的文件
        - has_previous: 是否有历史快照可对比
        - found_match: 是否找到了合适的对比快照
        - last_snapshot_time: 对比快照的时间
        - snapshot_id: 对比快照的ID
    """
    snapshots = _load_snapshots()
    
    # 没有任何历史快照
    if not snapshots:
        return {
            "added": files,
            "removed": [],
            "modified": [],
            "unchanged": [],
            "has_previous": False,
            "found_match": False,
            "last_snapshot_time": "",
            "snapshot_id": "",
            "nearest_snapshot_time": "",
        }

    # 找到最合适的对比快照
    # 优先找 scan_days 天前创建的快照，如果没有则往前推进找更早的快照
    # 使用日历天数逻辑：scan_days=1 表示昨天0点开始
    from datetime import datetime, timedelta
    
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # 例如：今天5月28日，scan_days=1 -> 目标时间是5月27日0点
    # 例如：今天5月28日，scan_days=7 -> 目标时间是5月21日0点
    target_time = today_start - timedelta(days=scan_days - 1)
    
    best_snapshot = None
    found_match = False
    
    # 找在 target_time 之前创建的最接近的快照（越接近 target_time 越好）
    valid_snapshots = []
    for s in snapshots:
        try:
            snapshot_time = datetime.fromisoformat(s.get("timestamp", ""))
            if snapshot_time <= target_time:
                valid_snapshots.append((snapshot_time, s))
        except (ValueError, TypeError):
            continue
    
    if valid_snapshots:
        # 按时间倒序排序，找最接近 target_time 的快照
        valid_snapshots.sort(key=lambda x: x[0], reverse=True)
        best_snapshot = valid_snapshots[0][1]
        found_match = True
    
    # 没有找到比 scan_days 更早的快照，所有文件都当作新增
    if not found_match:
        # 找最近的快照时间（用于提示用户）
        nearest_snapshot_time = ""
        if snapshots:
            try:
                nearest = max(
                    snapshots,
                    key=lambda s: datetime.fromisoformat(s.get("timestamp", "2000-01-01"))
                )
                nearest_time = datetime.fromisoformat(nearest.get("timestamp", ""))
                days_ago = (datetime.now() - nearest_time).days
                nearest_snapshot_time = f"{days_ago}天前"
            except (ValueError, TypeError):
                nearest_snapshot_time = "未知"
        
        return {
            "added": files,
            "removed": [],
            "modified": [],
            "unchanged": [],
            "has_previous": True,
            "found_match": False,
            "last_snapshot_time": "",
            "snapshot_id": "",
            "nearest_snapshot_time": nearest_snapshot_time,
        }

    # 构建旧文件的哈希映射
    old_hashes = {}
    for old_file in best_snapshot.get("files", []):
        old_hashes[old_file.get("path", "")] = old_file.get("hash", "")

    # 构建新文件的哈希映射
    new_hashes = {}
    for new_file in files:
        file_path = new_file.get("path", "")
        new_hashes[file_path] = _get_file_hash(file_path)

    added = []
    removed = []
    modified = []
    unchanged = []

    # 检查新增和修改的文件
    for new_file in files:
        file_path = new_file.get("path", "")
        new_hash = new_hashes.get(file_path)

        if file_path not in old_hashes:
            added.append(new_file)
        elif old_hashes[file_path] != new_hash:
            modified.append(new_file)
            # 添加旧文件信息用于比较
            for old_file in best_snapshot.get("files", []):
                if old_file.get("path") == file_path:
                    new_file["_old_modified"] = old_file.get("modified", "")
                    break
        else:
            unchanged.append(new_file)

    # 检查删除的文件
    for old_file in best_snapshot.get("files", []):
        old_path = old_file.get("path", "")
        if old_path not in new_hashes:
            removed.append(old_file)

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged": unchanged,
        "has_previous": True,
        "found_match": found_match,
        "last_snapshot_time": best_snapshot.get("timestamp", ""),
        "snapshot_id": best_snapshot.get("id", ""),
        "nearest_snapshot_time": "",
    }


def get_file_changes(file_path: str, limit: int = 5) -> List[Dict]:
    """获取某个文件的变更历史。

    Parameters
    ----------
    file_path : str
        文件路径。
    limit : int
        返回的最大记录数。

    Returns
    -------
    list[dict]
        文件变更历史列表。
    """
    snapshots = _load_snapshots()
    changes = []

    for snapshot in reversed(snapshots):
        for file_info in snapshot.get("files", []):
            if file_info.get("path") == file_path:
                changes.append({
                    "snapshot_id": snapshot.get("id", ""),
                    "timestamp": snapshot.get("timestamp", ""),
                    "modified": file_info.get("modified", ""),
                    "hash": file_info.get("hash", ""),
                })
                break

        if len(changes) >= limit:
            break

    return changes


def get_snapshot_file_contents(snapshot: Optional[Dict] = None) -> Dict[str, str]:
    """从快照中获取文件内容映射。

    Parameters
    ----------
    snapshot : dict, optional
        快照对象。如果为 None，使用最新快照。

    Returns
    -------
    dict[str, str]
        文件路径 -> 文件内容的映射。仅包含快照中存储了内容的文件。
    """
    if snapshot is None:
        snapshot = get_latest_snapshot()
    
    if not snapshot:
        return {}
    
    contents = {}
    for file_info in snapshot.get("files", []):
        file_path = file_info.get("path", "")
        file_content = file_info.get("content", "")
        if file_path and file_content:
            contents[file_path] = file_content
    
    return contents


def delete_snapshot(snapshot_id: str) -> bool:
    """删除指定的快照。

    Parameters
    ----------
    snapshot_id : str
        快照ID。

    Returns
    -------
    bool
        删除是否成功。
    """
    snapshots = _load_snapshots()
    original_count = len(snapshots)

    snapshots = [s for s in snapshots if s.get("id") != snapshot_id]

    if len(snapshots) == original_count:
        logger.warning("快照不存在: %s", snapshot_id)
        return False

    try:
        _SNAPSHOTS_FILE.write_text(
            json.dumps(snapshots, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info("删除快照成功: %s", snapshot_id)
        return True
    except Exception as e:
        logger.error("删除快照失败: %s", e)
        return False


def clear_old_snapshots(days: int = 30) -> int:
    """清理旧的快照。

    Parameters
    ----------
    days : int
        保留最近多少天的快照。

    Returns
    -------
    int
        删除的快照数量。
    """
    snapshots = _load_snapshots()
    cutoff = datetime.now() - timedelta(days=days)

    filtered = []
    deleted_count = 0

    for snapshot in snapshots:
        try:
            timestamp = datetime.fromisoformat(snapshot.get("timestamp", ""))
            if timestamp >= cutoff:
                filtered.append(snapshot)
            else:
                deleted_count += 1
        except ValueError:
            # 保留无法解析时间的快照
            filtered.append(snapshot)

    if deleted_count > 0:
        try:
            _SNAPSHOTS_FILE.write_text(
                json.dumps(filtered, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.info("清理了 %d 个旧快照", deleted_count)
        except Exception as e:
            logger.error("清理旧快照失败: %s", e)
            return 0

    return deleted_count


def get_timeline_summary() -> Dict:
    """获取时间线摘要信息。

    Returns
    -------
    dict
        包含快照数量、最近快照时间等信息。
    """
    snapshots = _load_snapshots()

    if not snapshots:
        return {
            "total_snapshots": 0,
            "latest_time": None,
            "oldest_time": None,
        }

    return {
        "total_snapshots": len(snapshots),
        "latest_time": snapshots[-1].get("timestamp"),
        "oldest_time": snapshots[0].get("timestamp"),
    }

"""Report generation module for weekly report agent.

Combines multiple file analysis results into a structured weekly report
using the generate.txt prompt template and an LLM provider.
"""

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from llm.base import (
    LLMProvider,
    LLMProviderError,
    RateLimitError,
    NetworkError,
)
from core.template_manager import get_template, list_templates

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
_GENERATE_TEMPLATE_PATH = _PROMPT_DIR / "generate.txt"

# Retry config for rate-limit errors (mirrors analyzer.py)
_MAX_RETRIES = 3
_RETRY_DELAY = 2  # seconds


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def get_week_range(ref_date: Optional[date] = None, days: int = 7) -> str:
    """Calculate the date range string from today going back *days* days.

    Parameters
    ----------
    ref_date : date, optional
        Reference date (end date). Defaults to ``date.today()``.
    days : int
        Number of days to look back (default 7).

    Returns
    -------
    str
        Formatted as ``"MM.DD - MM.DD"`` (start_date - end_date).
    """
    if ref_date is None:
        ref_date = date.today()

    # Start date is today minus (days-1) days
    start_date = ref_date - timedelta(days=days - 1)
    end_date = ref_date

    return f"{start_date.strftime('%m.%d')} - {end_date.strftime('%m.%d')}"


# ---------------------------------------------------------------------------
# Template & formatting helpers
# ---------------------------------------------------------------------------

def _load_template(template_name: Optional[str] = None) -> str:
    """Load the generate prompt template.

    Parameters
    ----------
    template_name : str, optional
        Name of the template to load (e.g. "standard", "concise", "detailed").
        If None, falls back to the default generate.txt template.

    Returns
    -------
    str
        Raw template text with ``{week_range}`` and ``{analyses}`` placeholders.

    Raises
    ------
    FileNotFoundError
        If the template file does not exist.
    """
    # If template_name is specified, try to load from template manager
    if template_name:
        template_data = get_template(template_name)
        if template_data is not None:
            logger.info("Loaded template: %s", template_name)
            return template_data["template"]
        logger.warning("Template '%s' not found, falling back to default", template_name)

    # Fall back to default generate.txt
    if not _GENERATE_TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Prompt template not found: {_GENERATE_TEMPLATE_PATH}"
        )
    return _GENERATE_TEMPLATE_PATH.read_text(encoding="utf-8")


def _format_analyses(analyses: List[Dict], file_changes: Optional[Dict] = None) -> str:
    """Format successful analyses into a single string for the template.

    Each entry is rendered as a labelled block so the LLM can distinguish
    individual files. Failed analyses (status != ``"success"``) are skipped.

    Parameters
    ----------
    analyses : list[dict]
        Raw analysis result dicts (from ``analyzer.analyze_all_files``).
    file_changes : dict, optional
        File changes information for incremental reports.
        Can be either:
        - Per-file format: ``{"file_path": {"added_lines": 10, "removed_lines": 5}}``
        - Categorized format: ``{"added": [...], "modified": [...], "removed": [...]}``

    Returns
    -------
    str
        Concatenated analysis text with optional change summary, or a
        placeholder message when empty.
    """
    successful = [a for a in analyses if a.get("status") == "success"]

    if not successful:
        return "（暂无文件分析结果）"

    # Build change summary if file_changes provided
    change_summary = ""
    if file_changes:
        summary_parts: List[str] = []

        # Handle per-file format: {"file_path": {"added_lines": N, "removed_lines": N}}
        if any(isinstance(v, dict) and "added_lines" in v for v in file_changes.values()):
            summary_parts.append("## 文件变更摘要")
            for fpath, stats in file_changes.items():
                added = stats.get("added_lines", 0)
                removed = stats.get("removed_lines", 0)
                if added > 0 or removed > 0:
                    fname = Path(fpath).name
                    parts = []
                    if added > 0:
                        parts.append(f"新增 {added} 行")
                    if removed > 0:
                        parts.append(f"删除 {removed} 行")
                    summary_parts.append(f"- 文件 {fname}（{fpath}）（{'，'.join(parts)}）")

        # Handle categorized format: {"added": [...], "modified": [...], "removed": [...]}
        elif "added" in file_changes or "modified" in file_changes or "removed" in file_changes:
            added = file_changes.get("added", [])
            modified = file_changes.get("modified", [])
            removed = file_changes.get("removed", [])

            if added or modified or removed:
                summary_parts.append("## 文件变更摘要")
                total_added = len(added)
                total_modified = len(modified)
                total_removed = len(removed)
                summary_parts.append(f"本次变更：新增 {total_added} 个文件，修改 {total_modified} 个文件，删除 {total_removed} 个文件")
                summary_parts.append("")

                if added:
                    summary_parts.append("### 新增文件")
                    for f in added[:10]:
                        fname = f.get("name", "") if isinstance(f, dict) else f
                        frel = f.get("relative", "") if isinstance(f, dict) else ""
                        line_info = ""
                        if isinstance(f, dict) and "added_lines" in f:
                            line_info = f"（新增 {f['added_lines']} 行）"
                        summary_parts.append(f"- {fname}（{frel}）{line_info}")
                    summary_parts.append("")

                if modified:
                    summary_parts.append("### 修改文件")
                    for f in modified[:10]:
                        fname = f.get("name", "") if isinstance(f, dict) else f
                        frel = f.get("relative", "") if isinstance(f, dict) else ""
                        line_info = ""
                        if isinstance(f, dict):
                            al = f.get("added_lines", 0)
                            rl = f.get("removed_lines", 0)
                            if al > 0 or rl > 0:
                                parts = []
                                if al > 0:
                                    parts.append(f"新增 {al} 行")
                                if rl > 0:
                                    parts.append(f"删除 {rl} 行")
                                line_info = f"（{'，'.join(parts)}）"
                        summary_parts.append(f"- {fname}（{frel}）{line_info}")
                    summary_parts.append("")

        if summary_parts:
            change_summary = "\n".join(summary_parts) + "\n\n"

    blocks: List[str] = []
    for idx, item in enumerate(successful, start=1):
        file_name = item.get("file_name", "unknown")
        file_path = item.get("file_path", "")
        analysis = item.get("analysis", "").strip()

        header = f"### 文件 {idx}: {file_name}"
        if file_path:
            header += f"（{file_path}）"

        blocks.append(f"{header}\n{analysis}")

    return change_summary + "\n\n".join(blocks)


def _build_messages(
    template: str,
    week_range: str,
    analyses: str,
    previous_report: Optional[str] = None,
    file_changes: Optional[Dict] = None,
) -> List[Dict[str, str]]:
    """Build the message list for LLM chat completion.

    Parameters
    ----------
    template : str
        Raw prompt template with placeholders.
    week_range : str
        Date range string (e.g. ``"05.19 - 05.25"``).
    analyses : str
        Pre-formatted analyses text.
    previous_report : str, optional
        Previous report content for comparison.
    file_changes : dict, optional
        File changes information.

    Returns
    -------
    list[dict]
        Messages list suitable for ``provider.chat_completion()``.
    """
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 构建增量对比信息
    incremental_info = ""
    if previous_report:
        incremental_info += "\n\n## 上次工作汇总（用于对比）\n"
        incremental_info += "请对比以下上次的工作汇总，重点关注新增和修改的内容，避免重复汇报已完成的工作：\n\n"
        # 增大限制到5000字符，让LLM完整学习模板内容
        incremental_info += previous_report[:5000]
        incremental_info += "\n\n"
    
    if file_changes:
        added = file_changes.get("added", [])
        modified = file_changes.get("modified", [])
        removed = file_changes.get("removed", [])
        
        if added or modified or removed:
            incremental_info += "## 本次文件变更情况\n"
            incremental_info += "以下文件发生了变更，请重点分析这些文件的变化内容：\n\n"
            
            if added:
                incremental_info += f"### 新增文件 ({len(added)} 个)\n"
                incremental_info += "这些是全新添加的文件，请完整介绍其功能和作用：\n"
                for f in added[:10]:  # 限制显示数量
                    fname = f.get("name", "") if isinstance(f, dict) else f
                    frel = f.get("relative", "") if isinstance(f, dict) else ""
                    line_info = ""
                    if isinstance(f, dict) and "added_lines" in f:
                        line_info = f"，新增 {f['added_lines']} 行"
                    incremental_info += f"- {fname}（{frel}）{line_info}\n"
                incremental_info += "\n"
            
            if modified:
                incremental_info += f"### 修改文件 ({len(modified)} 个)\n"
                incremental_info += "这些是已有文件的修改，请重点关注变更部分，避免重复描述未修改的内容：\n"
                for f in modified[:10]:
                    fname = f.get("name", "") if isinstance(f, dict) else f
                    frel = f.get("relative", "") if isinstance(f, dict) else ""
                    line_info = ""
                    if isinstance(f, dict):
                        al = f.get("added_lines", 0)
                        rl = f.get("removed_lines", 0)
                        if al > 0 or rl > 0:
                            parts = []
                            if al > 0:
                                parts.append(f"新增 {al} 行")
                            if rl > 0:
                                parts.append(f"删除 {rl} 行")
                            line_info = f"（{'，'.join(parts)}）"
                    incremental_info += f"- {fname}（{frel}）{line_info}\n"
                incremental_info += "\n"
            
            if removed:
                incremental_info += f"### 删除文件 ({len(removed)} 个)\n"
                incremental_info += "这些文件已被删除，请简要说明删除原因（如重构、功能移除等）：\n"
                for f in removed[:10]:
                    fname = f.get("name", "") if isinstance(f, dict) else f
                    incremental_info += f"- {fname}\n"
                incremental_info += "\n"
            
            incremental_info += "### 分析重点\n"
            incremental_info += "1. 对于新增文件：完整介绍功能、架构和作用\n"
            incremental_info += "2. 对于修改文件：仅描述变更内容，不要重复已有功能\n"
            incremental_info += "3. 对于删除文件：简要说明删除原因和影响\n"
    
    # 如果有增量信息，使用更精确的插入方式
    if incremental_info:
        # 查找"汇总生成要求"标记的位置（使用行级别匹配）
        lines = template.split('\n')
        insert_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith('## 汇总生成要求'):
                insert_idx = i
                break
        
        if insert_idx is not None:
            # 在"汇总生成要求"之前插入增量信息
            lines.insert(insert_idx, incremental_info.rstrip())
            template = '\n'.join(lines)
        else:
            # 如果没有找到标记，在末尾添加
            template += incremental_info
    
    prompt = template.format(
        week_range=week_range,
        analyses=analyses,
        current_date=current_date,
    )
    return [{"role": "user", "content": prompt}]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_report(
    analyses: List[Dict],
    provider: LLMProvider,
    week_range: Optional[str] = None,
    template_name: Optional[str] = None,
    previous_report: Optional[str] = None,
    file_changes: Optional[Dict] = None,
) -> str:
    """Generate a weekly report from file analysis results.

    Parameters
    ----------
    analyses : list[dict]
        List of analysis result dicts produced by ``analyzer.analyze_all_files``.
        Each dict must have at least ``status`` and ``analysis`` keys.
    provider : LLMProvider
        An initialised LLM provider instance for chat completion.
    week_range : str, optional
        Explicit date range string (e.g. ``"05.19 - 05.25"``).
        When *None*, the current week (Monday–Sunday) is calculated automatically.
    template_name : str, optional
        Name of the template to use (e.g. "standard", "concise", "detailed").
        If None, uses the default template from prompts/generate.txt.
    previous_report : str, optional
        Previous report content for comparison and incremental updates.
    file_changes : dict, optional
        File changes information with keys: added, modified, removed, unchanged.

    Returns
    -------
    str
        The generated weekly report in Markdown format.

    Raises
    ------
    FileNotFoundError
        If the generate prompt template is missing.
    LLMProviderError
        If the LLM call fails after all retries.
    ValueError
        If all analyses failed and no content can be provided.
    """
    # --- Resolve date range ---
    if not week_range:
        week_range = get_week_range()
        logger.info("Auto-calculated week range: %s", week_range)

    # --- Load template ---
    template = _load_template(template_name)

    # --- Format analyses (filter failures) ---
    formatted = _format_analyses(analyses, file_changes)
    logger.info(
        "Generating report for %d analyses (%d successful)",
        len(analyses),
        sum(1 for a in analyses if a.get("status") == "success"),
    )

    # --- Build messages ---
    messages = _build_messages(template, week_range, formatted, previous_report, file_changes)

    # --- Call LLM with retry for rate-limit / network errors ---
    last_error: Optional[str] = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = provider.chat_completion(
                messages=messages,
                temperature=0.5,
                max_tokens=4096,
            )

            if not response or not response.strip():
                last_error = "LLM returned an empty response"
                logger.warning(
                    "Empty response on attempt %d/%d", attempt, _MAX_RETRIES,
                )
                continue

            logger.info("Report generated successfully (%d chars)", len(response))
            
            report = response.strip()
            
            # 确保日期占位符被替换（LLM可能没有替换）
            from datetime import datetime
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            report = report.replace("{current_date}", current_date)
            
            return report

        except RateLimitError as exc:
            last_error = f"Rate limit exceeded: {exc}"
            logger.warning(
                "Rate limited (attempt %d/%d), retrying...",
                attempt, _MAX_RETRIES,
            )
            import time
            time.sleep(_RETRY_DELAY * attempt)

        except NetworkError as exc:
            last_error = f"Network error: {exc}"
            logger.error("Network error generating report: %s", exc)
            import time
            time.sleep(_RETRY_DELAY * attempt)

        except LLMProviderError as exc:
            last_error = f"LLM error: {exc}"
            logger.error("LLM error generating report: %s", exc)
            break  # Non-retryable

        except Exception as exc:
            last_error = f"Unexpected error: {exc}"
            logger.exception("Unexpected error generating report")
            break

    # All retries exhausted or non-retryable error
    raise LLMProviderError(
        f"Failed to generate report after {_MAX_RETRIES} attempts: {last_error}"
    )

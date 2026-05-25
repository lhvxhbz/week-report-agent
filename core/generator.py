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

def get_week_range(ref_date: Optional[date] = None) -> str:
    """Calculate the week range string (Monday–Sunday) containing *ref_date*.

    Parameters
    ----------
    ref_date : date, optional
        Reference date. Defaults to ``date.today()``.

    Returns
    -------
    str
        Formatted as ``"MM.DD - MM.DD"`` (Monday through Sunday).
    """
    if ref_date is None:
        ref_date = date.today()

    # Monday of the current ISO week (weekday(): Monday=0 … Sunday=6)
    monday = ref_date - timedelta(days=ref_date.weekday())
    sunday = monday + timedelta(days=6)

    return f"{monday.strftime('%m.%d')} - {sunday.strftime('%m.%d')}"


# ---------------------------------------------------------------------------
# Template & formatting helpers
# ---------------------------------------------------------------------------

def _load_template() -> str:
    """Load the generate prompt template from disk.

    Returns
    -------
    str
        Raw template text with ``{week_range}`` and ``{analyses}`` placeholders.

    Raises
    ------
    FileNotFoundError
        If the template file does not exist.
    """
    if not _GENERATE_TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Prompt template not found: {_GENERATE_TEMPLATE_PATH}"
        )
    return _GENERATE_TEMPLATE_PATH.read_text(encoding="utf-8")


def _format_analyses(analyses: List[Dict]) -> str:
    """Format successful analyses into a single string for the template.

    Each entry is rendered as a labelled block so the LLM can distinguish
    individual files. Failed analyses (status != ``"success"``) are skipped.

    Parameters
    ----------
    analyses : list[dict]
        Raw analysis result dicts (from ``analyzer.analyze_all_files``).

    Returns
    -------
    str
        Concatenated analysis text, or a placeholder message when empty.
    """
    successful = [a for a in analyses if a.get("status") == "success"]

    if not successful:
        return "（暂无文件分析结果）"

    blocks: List[str] = []
    for idx, item in enumerate(successful, start=1):
        file_name = item.get("file_name", "unknown")
        file_path = item.get("file_path", "")
        analysis = item.get("analysis", "").strip()

        header = f"### 文件 {idx}: {file_name}"
        if file_path:
            header += f"（{file_path}）"

        blocks.append(f"{header}\n{analysis}")

    return "\n\n".join(blocks)


def _build_messages(template: str, week_range: str, analyses: str) -> List[Dict[str, str]]:
    """Build the message list for LLM chat completion.

    Parameters
    ----------
    template : str
        Raw prompt template with placeholders.
    week_range : str
        Date range string (e.g. ``"05.19 - 05.25"``).
    analyses : str
        Pre-formatted analyses text.

    Returns
    -------
    list[dict]
        Messages list suitable for ``provider.chat_completion()``.
    """
    prompt = template.format(
        week_range=week_range,
        analyses=analyses,
    )
    return [{"role": "user", "content": prompt}]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_report(
    analyses: List[Dict],
    provider: LLMProvider,
    week_range: Optional[str] = None,
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
    template = _load_template()

    # --- Format analyses (filter failures) ---
    formatted = _format_analyses(analyses)
    logger.info(
        "Generating report for %d analyses (%d successful)",
        len(analyses),
        sum(1 for a in analyses if a.get("status") == "success"),
    )

    # --- Build messages ---
    messages = _build_messages(template, week_range, formatted)

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
            return response.strip()

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

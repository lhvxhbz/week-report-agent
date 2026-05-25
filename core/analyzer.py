"""File content analysis module for weekly report agent.

Calls LLM to analyze individual files and extract key work information
using the analyze.txt prompt template.
"""

import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

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
_ANALYZE_TEMPLATE_PATH = _PROMPT_DIR / "analyze.txt"

# Retry config for rate-limit errors
_MAX_RETRIES = 3
_RETRY_DELAY = 2  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_template() -> str:
    """Load the analyze prompt template from disk.

    Returns
    -------
    str
        Raw template text with {file_name}, {file_path}, {file_content} placeholders.

    Raises
    ------
    FileNotFoundError
        If the template file does not exist.
    """
    if not _ANALYZE_TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Prompt template not found: {_ANALYZE_TEMPLATE_PATH}"
        )
    return _ANALYZE_TEMPLATE_PATH.read_text(encoding="utf-8")


def _build_messages(
    template: str,
    file_info: Dict,
    file_content: str,
) -> List[Dict[str, str]]:
    """Build the message list for the LLM chat completion.

    Parameters
    ----------
    template : str
        Raw prompt template with placeholders.
    file_info : dict
        File metadata dict (must contain 'name' and 'relative' or 'path').
    file_content : str
        The file's text content.

    Returns
    -------
    list[dict]
        Messages list suitable for provider.chat_completion().
    """
    prompt = template.format(
        file_name=file_info.get("name", "unknown"),
        file_path=file_info.get("relative", file_info.get("path", "unknown")),
        file_content=file_content,
    )
    return [{"role": "user", "content": prompt}]


def _build_error_result(file_info: Dict, error_msg: str) -> Dict:
    """Build an error result dict for a failed analysis."""
    return {
        "file_name": file_info.get("name", "unknown"),
        "file_path": file_info.get("relative", file_info.get("path", "unknown")),
        "analysis": "",
        "status": "error",
        "error": error_msg,
    }


def _build_success_result(file_info: Dict, analysis: str) -> Dict:
    """Build a success result dict for a completed analysis."""
    return {
        "file_name": file_info.get("name", "unknown"),
        "file_path": file_info.get("relative", file_info.get("path", "unknown")),
        "analysis": analysis,
        "status": "success",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _analyze_with_template(
    file_info: Dict,
    provider: LLMProvider,
    template: str,
) -> Dict:
    """Internal: analyze a single file using a pre-loaded template.

    Parameters
    ----------
    file_info : dict
        File metadata dict from file_reader.scan_folder().
    provider : LLMProvider
        An initialized LLM provider instance.
    template : str
        Pre-loaded prompt template string.

    Returns
    -------
    dict
        Analysis result dict (see analyze_single_file for schema).
    """
    from core.file_reader import read_file

    # --- Read file content ---
    file_path = file_info.get("path", "")
    if not file_path:
        return _build_error_result(file_info, "File path is empty in file_info")

    content = read_file(file_path)

    # Check for read errors (read_file returns error strings prefixed with [Error] or [Skipped])
    if content.startswith("[Error]") or content.startswith("[Skipped]"):
        logger.warning("Could not read %s: %s", file_path, content)
        return _build_error_result(file_info, content)

    # --- Build messages ---
    messages = _build_messages(template, file_info, content)

    # --- Call LLM with retry for rate-limit / network errors ---
    last_error: Optional[str] = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = provider.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )

            # Validate response
            if not response or not response.strip():
                last_error = "LLM returned an empty response"
                logger.warning(
                    "Empty response for %s (attempt %d/%d)",
                    file_path, attempt, _MAX_RETRIES,
                )
                continue

            return _build_success_result(file_info, response.strip())

        except RateLimitError as exc:
            last_error = f"Rate limit exceeded: {exc}"
            logger.warning(
                "Rate limited on %s (attempt %d/%d), retrying...",
                file_path, attempt, _MAX_RETRIES,
            )
            import time
            time.sleep(_RETRY_DELAY * attempt)

        except NetworkError as exc:
            last_error = f"Network error: {exc}"
            logger.error("Network error analyzing %s: %s", file_path, exc)
            import time
            time.sleep(_RETRY_DELAY * attempt)

        except LLMProviderError as exc:
            last_error = f"LLM error: {exc}"
            logger.error("LLM error analyzing %s: %s", file_path, exc)
            # Non-retryable LLM errors (APIKeyError, ModelNotFoundError, etc.)
            break

        except Exception as exc:
            last_error = f"Unexpected error: {exc}"
            logger.exception("Unexpected error analyzing %s", file_path)
            break

    # All retries exhausted or non-retryable error
    return _build_error_result(file_info, last_error or "Unknown error after retries")


def analyze_single_file(file_info: Dict, provider: LLMProvider) -> Dict:
    """Analyze a single file by calling the LLM with the analyze prompt template.

    Parameters
    ----------
    file_info : dict
        File metadata dict from file_reader.scan_folder(). Must contain at least
        'path' (absolute path) and 'name'. May also contain 'relative', 'ext', etc.
    provider : LLMProvider
        An initialized LLM provider instance for chat completion.

    Returns
    -------
    dict
        Analysis result with keys:
        - file_name (str): The file's name.
        - file_path (str): The file's relative path.
        - analysis (str): LLM-generated analysis text.
        - status (str): 'success' or 'error'.
        - error (str): Error message (only present when status is 'error').
    """
    try:
        template = _load_template()
    except FileNotFoundError as exc:
        logger.error("Failed to load prompt template: %s", exc)
        return _build_error_result(file_info, str(exc))

    return _analyze_with_template(file_info, provider, template)


def analyze_all_files(
    files: List[Dict],
    provider: LLMProvider,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[Dict]:
    """Analyze multiple files sequentially using the LLM.

    Parameters
    ----------
    files : list[dict]
        List of file metadata dicts from file_reader.scan_folder().
    provider : LLMProvider
        An initialized LLM provider instance.
    progress_callback : callable, optional
        Callback function invoked after each file is processed.
        Signature: progress_callback(current: int, total: int)
        where current is 1-indexed and total is len(files).

    Returns
    -------
    list[dict]
        List of analysis result dicts, one per input file. Order matches input.
    """
    if not files:
        return []

    total = len(files)
    results: List[Dict] = []

    # Load template once for the batch
    try:
        template = _load_template()
    except FileNotFoundError as exc:
        logger.error("Failed to load prompt template: %s", exc)
        # Return error for all files
        return [_build_error_result(f, str(exc)) for f in files]

    logger.info("Starting analysis of %d files", total)

    for idx, file_info in enumerate(files, start=1):
        logger.debug("Analyzing file %d/%d: %s", idx, total, file_info.get("name", "?"))

        result = _analyze_with_template(file_info, provider, template)
        results.append(result)

        # Report progress
        if progress_callback is not None:
            try:
                progress_callback(idx, total)
            except Exception:
                logger.debug("Progress callback raised an exception", exc_info=True)

    # Summary logging
    successes = sum(1 for r in results if r["status"] == "success")
    errors = total - successes
    logger.info("Analysis complete: %d success, %d errors out of %d files", successes, errors, total)

    return results

"""File content analysis module for weekly report agent.

Calls LLM to analyze individual files and extract key work information
using the analyze.txt prompt template.
"""

import hashlib
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.file_reader import read_files_concurrent
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

# Concurrency settings - increased to 5
_MAX_LLM_WORKERS = 5  # Number of concurrent LLM calls

# Cache settings
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_CACHE_FILE = _CACHE_DIR / "analysis_cache.json"

# Error rate monitoring
_error_stats = {
    "total": 0,
    "success": 0,
    "errors": 0,
    "rate_limit": 0,
    "network": 0,
    "timeout": 0,
}
_stats_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------

def _load_cache() -> Dict:
    """Load analysis cache from disk."""
    if _CACHE_FILE.exists():
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load cache: %s", e)
    return {}


def _save_cache(cache: Dict) -> None:
    """Save analysis cache to disk."""
    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Failed to save cache: %s", e)


def _get_file_hash(file_path: str) -> str:
    """Get a hash based on file path and modification time for cache key."""
    try:
        stat = os.stat(file_path)
        # Use path + mtime + size as cache key
        key = f"{file_path}:{stat.st_mtime}:{stat.st_size}"
        return hashlib.md5(key.encode()).hexdigest()
    except OSError:
        return hashlib.md5(file_path.encode()).hexdigest()


def _get_cached_result(file_path: str, cache: Dict) -> Optional[Dict]:
    """Get cached analysis result if available and valid."""
    file_hash = _get_file_hash(file_path)
    if file_hash in cache:
        logger.debug("Cache hit for %s", file_path)
        return cache[file_hash]
    return None


def _cache_result(file_path: str, result: Dict, cache: Dict) -> None:
    """Cache an analysis result."""
    file_hash = _get_file_hash(file_path)
    cache[file_hash] = result


# ---------------------------------------------------------------------------
# Error Rate Monitoring
# ---------------------------------------------------------------------------

def _update_stats(success: bool, error_type: str = None) -> None:
    """Update error statistics."""
    with _stats_lock:
        _error_stats["total"] += 1
        if success:
            _error_stats["success"] += 1
        else:
            _error_stats["errors"] += 1
            if error_type == "rate_limit":
                _error_stats["rate_limit"] += 1
            elif error_type == "network":
                _error_stats["network"] += 1
            elif error_type == "timeout":
                _error_stats["timeout"] += 1


def get_error_stats() -> Dict:
    """Get current error statistics."""
    with _stats_lock:
        stats = _error_stats.copy()
        if stats["total"] > 0:
            stats["error_rate"] = stats["errors"] / stats["total"] * 100
        else:
            stats["error_rate"] = 0.0
        return stats


def reset_error_stats() -> None:
    """Reset error statistics."""
    with _stats_lock:
        _error_stats.update({
            "total": 0,
            "success": 0,
            "errors": 0,
            "rate_limit": 0,
            "network": 0,
            "timeout": 0,
        })


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
    file_content: Optional[str] = None,
    cache: Optional[Dict] = None,
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
    file_content : str, optional
        Pre-read file content. If None, reads the file via read_file().
    cache : dict, optional
        Analysis cache dict.

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

    # Check cache first
    if cache is not None:
        cached_result = _get_cached_result(file_path, cache)
        if cached_result is not None:
            logger.info("Using cached result for %s", file_path)
            _update_stats(True)
            return cached_result

    if file_content is None:
        content = read_file(file_path)
    else:
        content = file_content

    # Check for read errors (read_file returns error strings prefixed with [Error] or [Skipped])
    if content.startswith("[Error]") or content.startswith("[Skipped]"):
        logger.warning("Could not read %s: %s", file_path, content)
        _update_stats(False, "read_error")
        return _build_error_result(file_info, content)

    # --- Build messages ---
    messages = _build_messages(template, file_info, content)

    # --- Call LLM with retry for rate-limit / network errors ---
    last_error: Optional[str] = None
    error_type = None
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

            # Success - cache result and update stats
            result = _build_success_result(file_info, response.strip())
            if cache is not None:
                _cache_result(file_path, result, cache)
            _update_stats(True)
            return result

        except RateLimitError as exc:
            last_error = f"Rate limit exceeded: {exc}"
            error_type = "rate_limit"
            logger.warning(
                "Rate limited on %s (attempt %d/%d), retrying...",
                file_path, attempt, _MAX_RETRIES,
            )
            time.sleep(_RETRY_DELAY * attempt)

        except NetworkError as exc:
            last_error = f"Network error: {exc}"
            error_type = "network"
            logger.error("Network error analyzing %s: %s", file_path, exc)
            time.sleep(_RETRY_DELAY * attempt)

        except LLMProviderError as exc:
            last_error = f"LLM error: {exc}"
            error_type = "llm"
            logger.error("LLM error analyzing %s: %s", file_path, exc)
            # Non-retryable LLM errors (APIKeyError, ModelNotFoundError, etc.)
            break

        except Exception as exc:
            last_error = f"Unexpected error: {exc}"
            error_type = "unknown"
            logger.exception("Unexpected error analyzing %s", file_path)
            break

    # All retries exhausted or non-retryable error
    _update_stats(False, error_type)
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


def analyze_changes(
    file_info: Dict,
    provider: LLMProvider,
    old_content: Optional[str],
    new_content: str,
) -> Dict:
    """Analyze only the changes between old and new file content.

    For new files (old_content is None), the full new_content is analyzed.
    For modified files, only the diff between old and new content is analyzed,
    reducing token usage and focusing on recent work.

    Parameters
    ----------
    file_info : dict
        File metadata dict from file_reader.scan_folder(). Must contain at least
        'path' (absolute path) and 'name'. May also contain 'relative', 'ext', etc.
    provider : LLMProvider
        An initialized LLM provider instance for chat completion.
    old_content : str or None
        Previous file content. If None, the file is treated as new and
        the full new_content is analyzed.
    new_content : str
        Current file content.

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

    # Determine what content to analyze
    if old_content is None:
        # New file – analyze full content
        logger.info("New file detected, analyzing full content: %s", file_info.get("name", ""))
        content_to_analyze = new_content
    else:
        # Modified file – extract only the diff for analysis
        try:
            from core.diff_extractor import extract_changes_for_analysis
        except ImportError:
            logger.warning(
                "diff_extractor module not available, falling back to full content analysis"
            )
            content_to_analyze = new_content
        else:
            file_path = file_info.get("path", "")
            changes_text = extract_changes_for_analysis(file_path, old_content, new_content)

            if not changes_text or not changes_text.strip():
                logger.info("No meaningful changes detected in %s", file_path)
                return _build_success_result(
                    file_info, "近期无明显改动。"
                )

            content_to_analyze = changes_text
            logger.info(
                "Analyzing diff for %s (%d chars)",
                file_info.get("name", ""),
                len(changes_text),
            )

    # Build messages and call LLM via the existing internal helper
    return _analyze_with_template(file_info, provider, template, file_content=content_to_analyze)


def analyze_all_files(
    files: List[Dict],
    provider: LLMProvider,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    max_workers: int = _MAX_LLM_WORKERS,
    use_cache: bool = True,
) -> List[Dict]:
    """Analyze multiple files using the LLM with concurrent processing.

    Both file reading and LLM analysis run concurrently for maximum speed.
    Results are cached to avoid re-analyzing unchanged files.

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
    max_workers : int
        Maximum number of concurrent LLM calls (default 5).
    use_cache : bool
        Whether to use cache (default True).

    Returns
    -------
    list[dict]
        List of analysis result dicts, one per input file. Order matches input.
    """
    if not files:
        return []

    total = len(files)
    results: List[Dict] = [None] * total  # Pre-allocate to maintain order

    # Reset error stats for this batch
    reset_error_stats()

    # Load template once for the batch
    try:
        template = _load_template()
    except FileNotFoundError as exc:
        logger.error("Failed to load prompt template: %s", exc)
        return [_build_error_result(f, str(exc)) for f in files]

    # Load cache
    cache = _load_cache() if use_cache else {}
    cache_hits = 0

    # --- Pre-read all file contents concurrently ---
    file_paths = [f.get("path", "") for f in files]
    logger.info("Pre-reading %d files concurrently", total)
    file_contents = read_files_concurrent(file_paths, max_workers=4)

    logger.info("Starting concurrent analysis of %d files with %d workers", total, max_workers)

    # --- Progress tracking ---
    completed_count = 0
    progress_lock = threading.Lock()

    def _analyze_single(idx: int, file_info: Dict) -> Dict:
        """Analyze a single file and update progress."""
        nonlocal completed_count, cache_hits
        file_path = file_info.get("path", "")
        content = file_contents.get(file_path)
        
        # 检查是否是缓存命中（在调用前检查）
        if use_cache:
            cached_result = _get_cached_result(file_path, cache)
            if cached_result is not None:
                cache_hits += 1
        
        result = _analyze_with_template(
            file_info, provider, template, 
            file_content=content, cache=cache
        )

        # Update progress
        with progress_lock:
            completed_count += 1
            if progress_callback is not None:
                try:
                    progress_callback(completed_count, total)
                except Exception:
                    logger.debug("Progress callback raised an exception", exc_info=True)

        return result

    # --- Run LLM analysis concurrently ---
    effective_workers = min(max_workers, total)
    with ThreadPoolExecutor(max_workers=effective_workers) as executor:
        # Submit all tasks
        future_to_idx = {
            executor.submit(_analyze_single, idx, file_info): idx
            for idx, file_info in enumerate(files)
        }

        # Collect results as they complete
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                logger.exception("Unexpected error in concurrent analysis for file %d", idx)
                results[idx] = _build_error_result(files[idx], f"Unexpected error: {exc}")

    # Save cache
    if use_cache:
        _save_cache(cache)

    # Summary logging
    stats = get_error_stats()
    successes = sum(1 for r in results if r["status"] == "success")
    errors = total - successes
    
    logger.info(
        "Analysis complete: %d success, %d errors out of %d files "
        "(cache hits: %d, error rate: %.1f%%)",
        successes, errors, total, cache_hits, stats["error_rate"]
    )
    
    # Log warning if error rate is high
    if stats["error_rate"] > 20:
        logger.warning(
            "High error rate detected: %.1f%% "
            "(rate_limit: %d, network: %d, timeout: %d)",
            stats["error_rate"],
            stats["rate_limit"],
            stats["network"],
            stats["timeout"]
        )

    return results

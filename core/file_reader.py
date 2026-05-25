"""File scanning and reading module for weekly report agent.

Provides scan_folder() to discover recently modified files and read_file()
to extract content from various file formats.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Well-known directories to skip
_IGNORED_DIRS = frozenset({
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    ".git",
    ".svn",
    ".hg",
    ".idea",
    ".vscode",
    ".vs",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".eggs",
    "egg-info",
    ".cache",
    ".next",
    ".nuxt",
    "coverage",
    ".sass-cache",
    "bower_components",
    "jspm_packages",
    ".gradle",
    "target",
    "bin",
    "obj",
})

# Maximum file size: 1 MB
MAX_FILE_SIZE = 1 * 1024 * 1024

# Maximum recursion depth
MAX_DEPTH = 5

# Supported text file extensions for read_file()
_TEXT_EXTENSIONS = frozenset({
    ".txt",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".htm",
    ".css",
    ".json",
    ".csv",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".sh",
    ".bat",
    ".ps1",
    ".xml",
    ".svg",
    ".sql",
    ".r",
    ".rb",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".swift",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".lua",
    ".php",
    ".pl",
    ".log",
    ".env",
    ".gitignore",
    ".dockerignore",
    ".editorconfig",
    ".prettierrc",
    ".eslintrc",
    ".lock",
    ".makefile",
    ".cmake",
})

# Docx extension
_DOCX_EXTENSIONS = frozenset({".docx"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _should_skip_dir(dirname: str) -> bool:
    """Return True if directory should be skipped."""
    # Skip hidden directories
    if dirname.startswith("."):
        return True
    # Skip well-known ignored directories
    if dirname in _IGNORED_DIRS:
        return True
    # Also match patterns like package.egg-info
    if ".egg-info" in dirname:
        return True
    return False


def _format_mtime(timestamp: float) -> str:
    """Format a file's mtime as 'YYYY-MM-DD HH:MM'."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _read_docx(file_path: Path) -> str:
    """Read a .docx file using python-docx. Returns plain text content."""
    try:
        from docx import Document  # type: ignore[import-untyped]

        doc = Document(str(file_path))
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n".join(paragraphs)
    except ImportError:
        return "[Error] python-docx is not installed. Run: pip install python-docx"
    except Exception as exc:
        return f"[Error] Failed to read docx file: {exc}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_folder(folder_path: str, days: int = 7) -> List[Dict]:
    """Scan a folder and return files modified within the last *days* days.

    Parameters
    ----------
    folder_path : str
        Absolute or relative path to the folder to scan.
    days : int
        Number of days to look back (default 7).

    Returns
    -------
    list[dict]
        Each dict contains: path, name, relative, modified, size, ext.
    """
    root = Path(folder_path).resolve()
    if not root.is_dir():
        return []

    cutoff = datetime.now() - timedelta(days=days)
    cutoff_ts = cutoff.timestamp()
    results: List[Dict] = []

    def _walk(current: Path, depth: int) -> None:
        if depth > MAX_DEPTH:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda e: e.name)
        except PermissionError:
            return

        for entry in entries:
            try:
                # Directory handling
                if entry.is_dir():
                    if _should_skip_dir(entry.name):
                        continue
                    _walk(entry, depth + 1)
                    continue

                # File handling
                if not entry.is_file():
                    continue

                # Get file stats once
                try:
                    stat = entry.stat()
                    mtime = stat.st_mtime
                    size = stat.st_size
                except OSError:
                    continue

                # Skip files older than cutoff
                if mtime < cutoff_ts:
                    continue

                # Skip files exceeding max size
                if size > MAX_FILE_SIZE:
                    continue

                # Build result
                ext = entry.suffix.lower()
                rel = entry.relative_to(root)
                results.append(
                    {
                        "path": str(entry),
                        "name": entry.name,
                        "relative": str(rel),
                        "modified": _format_mtime(mtime),
                        "size": size,
                        "ext": ext,
                    }
                )
            except PermissionError:
                continue
            except OSError:
                continue

    _walk(root, depth=0)
    return results


def read_file(file_path: str) -> str:
    """Read the content of a file, supporting multiple formats.

    Supported formats include .txt, .md, .py, .js, .ts, .tsx, .html, .css,
    .json, .csv, .docx, and many more text-based formats.

    Parameters
    ----------
    file_path : str
        Path to the file to read.

    Returns
    -------
    str
        File content as a string, or an error/message string on failure.
    """
    path = Path(file_path)

    # Validate existence
    if not path.exists():
        return f"[Error] File not found: {file_path}"

    if not path.is_file():
        return f"[Error] Not a file: {file_path}"

    # Check file size before reading
    try:
        size = path.stat().st_size
    except OSError as exc:
        return f"[Error] Cannot access file: {exc}"

    if size == 0:
        return ""

    if size > MAX_FILE_SIZE:
        return (
            f"[Skipped] File exceeds 1 MB limit "
            f"({size / 1024 / 1024:.2f} MB): {file_path}"
        )

    ext = path.suffix.lower()

    # Handle .docx
    if ext in _DOCX_EXTENSIONS:
        return _read_docx(path)

    # Handle text-based files
    if ext in _TEXT_EXTENSIONS or ext == "":
        return _read_text_file(path)

    return f"[Skipped] Unsupported file format: {ext}"


def _read_text_file(path: Path) -> str:
    """Read a text file with encoding fallback."""
    encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            return f"[Error] Failed to read file: {exc}"
    return f"[Error] Unable to decode file with supported encodings: {path}"

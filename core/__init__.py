"""Core module for file reading, analysis, and report generation."""

from core.file_reader import read_file, scan_folder
from core.generator import generate_report, get_week_range
from core.template_manager import (
    list_templates,
    get_template,
    save_custom_template,
    delete_custom_template,
    extract_template_from_report,
)
from core.report_archive import (
    archive_report,
    list_archived_reports,
    get_archived_report,
    delete_archived_report,
    get_archive_stats,
)

__all__ = [
    "scan_folder",
    "read_file",
    "generate_report",
    "get_week_range",
    "list_templates",
    "get_template",
    "save_custom_template",
    "delete_custom_template",
    "extract_template_from_report",
    "archive_report",
    "list_archived_reports",
    "get_archived_report",
    "delete_archived_report",
    "get_archive_stats",
]

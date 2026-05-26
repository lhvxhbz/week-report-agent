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
]

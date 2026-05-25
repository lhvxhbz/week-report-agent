"""Core module for file reading, analysis, and report generation."""

from core.file_reader import read_file, scan_folder
from core.generator import generate_report, get_week_range

__all__ = ["scan_folder", "read_file", "generate_report", "get_week_range"]

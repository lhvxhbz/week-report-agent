"""周报终结者 V1 - Streamlit Web界面."""

import io
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import streamlit as st

# Ensure project root is on sys.path so local imports work
_project_root = str(Path(__file__).resolve().parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from config import Config  # noqa: E402
from core.file_reader import scan_folder  # noqa: E402
from core.analyzer import analyze_all_files  # noqa: E402
from core.generator import generate_report, get_week_range  # noqa: E402
from llm.factory import (  # noqa: E402
    create_provider,
    get_configured_providers,
    PROVIDER_DISPLAY_NAMES,
)
from llm.custom_provider import CustomProvider  # noqa: E402


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="周报终结者 V1",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / 1024 / 1024:.1f} MB"


def _file_icon(ext: str) -> str:
    """Return a simple icon string for a file extension."""
    icons = {
        ".py": "🐍",
        ".js": "📜",
        ".ts": "📘",
        ".tsx": "⚛️",
        ".jsx": "⚛️",
        ".html": "🌐",
        ".css": "🎨",
        ".json": "📋",
        ".md": "📝",
        ".txt": "📄",
        ".docx": "📘",
        ".pdf": "📕",
        ".yaml": "⚙️",
        ".yml": "⚙️",
        ".sh": "💻",
        ".sql": "🗃️",
        ".csv": "📊",
    }
    return icons.get(ext, "📄")


def _get_provider_choices() -> Tuple[List[str], Dict[str, str]]:
    """Return (display_names_list, display_to_key_mapping)."""
    configured = get_configured_providers()
    if not configured:
        return [], {}

    names = []
    mapping = {}
    for key in configured:
        display = PROVIDER_DISPLAY_NAMES.get(key, key)
        names.append(display)
        mapping[display] = key
    return names, mapping


def _md_to_txt(md_text: str) -> str:
    """Convert Markdown to plain text by stripping formatting."""
    text = re.sub(r"^#{1,6}\s+", "", md_text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"^[-*+]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^---+$", "─" * 40, text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _md_to_docx(md_text: str) -> bytes:
    """Convert Markdown text to a Word document (.docx)."""
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = "Microsoft YaHei"
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(6)

    lines = md_text.split("\n")
    in_code_block = False
    code_lines: List[str] = []

    for line in lines:
        if line.strip().startswith("```"):
            if in_code_block:
                if code_lines:
                    p = doc.add_paragraph()
                    run = p.add_run("\n".join(code_lines))
                    run.font.name = "Consolas"
                    run.font.size = Pt(9)
                code_lines = []
            in_code_block = not in_code_block
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("# "):
            h = doc.add_heading(stripped[2:].strip(), level=1)
            h.alignment = WD_ALIGN_PARAGRAPH.LEFT
        elif stripped.startswith("## "):
            doc.add_heading(stripped[3:].strip(), level=2)
        elif stripped.startswith("### "):
            doc.add_heading(stripped[4:].strip(), level=3)
        elif stripped.startswith("#### "):
            doc.add_heading(stripped[5:].strip(), level=4)
        elif stripped.startswith("---"):
            p = doc.add_paragraph()
            p.add_run("─" * 50)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped[2:])
            text = re.sub(r"\*(.+?)\*", r"\1", text)
            doc.add_paragraph(text, style="List Bullet")
        elif re.match(r"^\d+\.\s", stripped):
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
            text = re.sub(r"\d+\.\s", "", text, count=1)
            doc.add_paragraph(text, style="List Number")
        else:
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
            text = re.sub(r"\*(.+?)\*", r"\1", text)
            doc.add_paragraph(text)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def _md_to_pdf(md_text: str) -> bytes:
    """Convert Markdown text to PDF using fpdf2 with Chinese font support."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.add_page()

    # Try to load a Chinese font
    font_loaded = False
    font_paths = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\simfang.ttf",
    ]
    for font_path in font_paths:
        if Path(font_path).exists():
            try:
                pdf.add_font("Chinese", "", font_path, uni=True)
                pdf.set_font("Chinese", size=10)
                font_loaded = True
                break
            except Exception:
                continue

    if not font_loaded:
        pdf.set_font("Helvetica", size=10)

    def write_text(text: str, size: int = 10, bold: bool = False):
        """Helper to write text with proper font settings."""
        if font_loaded:
            pdf.set_font("Chinese", size=size)
        else:
            style = "B" if bold else ""
            pdf.set_font("Helvetica", style, size=size)
        # Ensure we're at left margin
        pdf.set_x(15)
        pdf.multi_cell(0, size * 0.5, text)

    lines = md_text.split("\n")
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            if font_loaded:
                pdf.set_font("Chinese", size=8)
            else:
                pdf.set_font("Courier", size=8)
            pdf.set_x(15)
            pdf.multi_cell(0, 4, stripped)
            if font_loaded:
                pdf.set_font("Chinese", size=10)
            else:
                pdf.set_font("Helvetica", size=10)
            continue

        if not stripped:
            pdf.ln(2)
            continue

        # Remove markdown formatting for PDF
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
        text = re.sub(r"\*(.+?)\*", r"\1", text)

        if stripped.startswith("# "):
            write_text(text[2:].strip(), size=16, bold=True)
            pdf.ln(2)
        elif stripped.startswith("## "):
            write_text(text[3:].strip(), size=13, bold=True)
            pdf.ln(1)
        elif stripped.startswith("### "):
            write_text(text[4:].strip(), size=11, bold=True)
            pdf.ln(1)
        elif stripped.startswith("#### "):
            write_text(text[5:].strip(), size=10, bold=True)
        elif stripped.startswith("---"):
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(3)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            content = text[2:].strip()
            write_text(f"  \u2022 {content}", size=10)
        elif re.match(r"^\d+\.\s", stripped):
            write_text(f"  {text}", size=10)
        else:
            write_text(text, size=10)

    return bytes(pdf.output())


def _get_export_data(report: str, fmt: str) -> Tuple[bytes, str, str]:
    """Get export data for the selected format.

    Returns:
        (data_bytes, filename, mime_type)
    """
    week_range = get_week_range()
    base_name = f"周报_{week_range.replace(' ', '').replace('-', '_')}"

    if fmt == "Markdown (.md)":
        return report.encode("utf-8"), f"{base_name}.md", "text/markdown"
    elif fmt == "纯文本 (.txt)":
        return _md_to_txt(report).encode("utf-8"), f"{base_name}.txt", "text/plain"
    elif fmt == "Word (.docx)":
        try:
            return _md_to_docx(report), f"{base_name}.docx", (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        except Exception as e:
            st.error(f"Word导出失败: {e}")
            return report.encode("utf-8"), f"{base_name}.md", "text/markdown"
    elif fmt == "PDF (.pdf)":
        try:
            pdf_data = _md_to_pdf(report)
            return pdf_data, f"{base_name}.pdf", "application/pdf"
        except Exception as e:
            st.error(f"PDF导出失败: {e}")
            return report.encode("utf-8"), f"{base_name}.md", "text/markdown"
    else:
        return report.encode("utf-8"), f"{base_name}.md", "text/markdown"


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

if "report" not in st.session_state:
    st.session_state.report = None
if "files" not in st.session_state:
    st.session_state.files = None
if "scan_done" not in st.session_state:
    st.session_state.scan_done = False
if "config_mode" not in st.session_state:
    st.session_state.config_mode = "使用 .env 配置"
if "manual_base_url" not in st.session_state:
    st.session_state.manual_base_url = ""
if "manual_api_key" not in st.session_state:
    st.session_state.manual_api_key = ""
if "manual_model_name" not in st.session_state:
    st.session_state.manual_model_name = ""


# ---------------------------------------------------------------------------
# Sidebar: Settings
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## ⚙️ 设置")

    # -- Working directory --
    default_dir = Config.SCAN_DIRS.split(",")[0].strip()
    if default_dir == ".":
        default_dir = str(Path(__file__).resolve().parent)
    work_dir = st.text_input(
        "📁 工作目录",
        value=default_dir,
        placeholder="输入要扫描的文件夹路径",
        help="输入要扫描的文件夹绝对路径或相对路径",
    )

    # -- Scan days --
    scan_days = st.slider(
        "📅 扫描天数",
        min_value=1,
        max_value=30,
        value=7,
        help="扫描最近N天内修改过的文件",
    )

    st.divider()

    # -- Model configuration mode --
    st.markdown("### 🤖 模型配置")

    config_mode = st.selectbox(
        "配置模式",
        options=["使用 .env 配置", "手动配置"],
        index=0,
        help="选择模型配置来源：使用环境变量文件或手动输入",
    )
    st.session_state.config_mode = config_mode

    selected_provider_key = None
    manual_provider = None

    if config_mode == "使用 .env 配置":
        # -- Model selection from .env --
        provider_display_list, display_to_key = _get_provider_choices()

        if provider_display_list:
            selected_display = st.selectbox(
                "🤖 模型选择",
                options=provider_display_list,
                help="自动检测已配置API Key的模型",
            )
            selected_provider_key = display_to_key[selected_display]
            st.caption(f"✅ 已检测到 {len(provider_display_list)} 个可用模型")
        else:
            selected_provider_key = None
            st.warning("⚠️ 未检测到已配置的API Key")
            st.caption("请在 `.env` 文件中配置至少一个模型的API Key")

    else:
        # -- Manual configuration --
        manual_base_url = st.text_input(
            "🌐 Base URL",
            value=st.session_state.manual_base_url,
            placeholder="https://api.example.com/v1",
            help="OpenAI兼容API的基础URL",
        )
        st.session_state.manual_base_url = manual_base_url

        manual_api_key = st.text_input(
            "🔑 API Key",
            value=st.session_state.manual_api_key,
            type="password",
            placeholder="sk-...",
            help="API密钥（可选，某些本地服务不需要）",
        )
        st.session_state.manual_api_key = manual_api_key

        manual_model_name = st.text_input(
            "📦 模型名称",
            value=st.session_state.manual_model_name,
            placeholder="gpt-4o-mini",
            help="要使用的模型名称",
        )
        st.session_state.manual_model_name = manual_model_name

        if manual_base_url and manual_model_name:
            try:
                manual_provider = CustomProvider(
                    api_key=manual_api_key,
                    model=manual_model_name,
                    base_url=manual_base_url,
                )
                st.success("✅ 手动配置已就绪")
            except ValueError as e:
                st.error(f"配置错误: {e}")
        else:
            st.caption("请输入 Base URL 和模型名称")

    st.divider()

    # -- Usage tips --
    st.markdown("### 💡 使用提示")
    st.markdown(
        "1. 输入工作目录路径\n"
        "2. 选择扫描天数\n"
        "3. 配置AI模型\n"
        "4. 点击 **🚀 生成周报**\n"
        "5. 等待分析完成\n"
        "6. 选择格式并下载周报"
    )


# ---------------------------------------------------------------------------
# Main area: Title
# ---------------------------------------------------------------------------

st.markdown("# 📝 周报终结者 V1")
st.caption("自动扫描工作文件，AI生成结构化周报")


# ---------------------------------------------------------------------------
# Scan files
# ---------------------------------------------------------------------------

scan_col, _ = st.columns([1, 3])
with scan_col:
    if st.button("🔍 扫描文件", use_container_width=True):
        if not work_dir or not work_dir.strip():
            st.error("请输入有效的工作目录路径")
        else:
            resolved = Path(work_dir).resolve()
            if not resolved.is_dir():
                st.error(f"目录不存在: {resolved}")
            else:
                with st.spinner("正在扫描文件..."):
                    files = scan_folder(work_dir, days=scan_days)
                st.session_state.files = files
                st.session_state.scan_done = True
                st.session_state.report = None  # Reset report on new scan


# ---------------------------------------------------------------------------
# Stats cards + File list (after scan)
# ---------------------------------------------------------------------------

files = st.session_state.files

if st.session_state.scan_done and files is not None:
    total_files = len(files)
    total_size = sum(f["size"] for f in files)

    # -- Stats cards --
    m1, m2, m3 = st.columns(3)
    m1.metric("📄 文件数", f"{total_files}个")
    m2.metric("📅 范围", f"{scan_days}天")
    m3.metric("💾 总大小", _human_size(total_size))

    st.divider()

    # -- File list (expandable) --
    if total_files > 0:
        with st.expander(f"📄 文件列表 ({total_files}个文件)", expanded=False):
            for f in files:
                icon = _file_icon(f["ext"])
                st.markdown(
                    f"{icon} **{f['name']}**  \n"
                    f"<small>`{f['relative']}` · {_human_size(f['size'])} · {f['modified']}</small>",
                    unsafe_allow_html=True,
                )
    else:
        st.info("未找到最近修改的文件，请尝试增大扫描天数或更换目录")

    st.divider()

    # -- Determine if we have a valid provider --
    has_provider = False
    if config_mode == "使用 .env 配置":
        has_provider = selected_provider_key is not None
    else:
        has_provider = manual_provider is not None

    # -- Generate button --
    if total_files > 0 and has_provider:
        if st.button("🚀 生成周报", type="primary", use_container_width=True):
            # Phase 1: Analyze files with progress
            st.markdown("### 📊 分析进度")

            progress_bar = st.progress(0)
            status_text = st.empty()

            def _update_progress(current: int, total: int) -> None:
                pct = current / total
                progress_bar.progress(pct)
                status_text.text(f"分析中: {current}/{total} 个文件")

            try:
                # Create provider based on config mode
                if config_mode == "手动配置":
                    provider = manual_provider
                else:
                    provider = create_provider(selected_provider_key)

                analyses = analyze_all_files(files, provider, _update_progress)

                progress_bar.progress(1.0)
                status_text.text(f"✅ 分析完成: {len(analyses)} 个文件")

                # Phase 2: Generate report
                with st.spinner("正在生成周报..."):
                    report = generate_report(analyses, provider)

                st.session_state.report = report
                st.success("🎉 周报生成完成！")

            except ValueError as exc:
                st.error(f"配置错误: {exc}")
            except FileNotFoundError as exc:
                st.error(f"文件未找到: {exc}")
            except Exception as exc:
                st.error(f"生成失败: {exc}")

    elif total_files > 0 and not has_provider:
        if config_mode == "使用 .env 配置":
            st.warning("请先在 `.env` 文件中配置API Key，然后重启应用")
        else:
            st.warning("请在左侧填写完整的模型配置信息")

    # -- Report preview & download --
    if st.session_state.report:
        st.divider()
        st.markdown("### 📋 生成的周报")
        st.markdown(st.session_state.report)

        st.divider()
        st.markdown("### 📥 导出周报")

        export_format = st.selectbox(
            "选择导出格式",
            options=["Markdown (.md)", "纯文本 (.txt)", "Word (.docx)", "PDF (.pdf)"],
            index=0,
            help="选择要下载的文件格式",
        )

        # 根据选择的格式生成数据
        week_range = get_week_range()
        base_name = f"周报_{week_range.replace(' ', '').replace('-', '_')}"

        if export_format == "Markdown (.md)":
            download_data = st.session_state.report.encode("utf-8")
            download_filename = f"{base_name}.md"
            download_mime = "text/markdown"
            st.success(f"✅ Markdown生成成功 ({len(download_data)} 字节)")
        elif export_format == "纯文本 (.txt)":
            download_data = _md_to_txt(st.session_state.report).encode("utf-8")
            download_filename = f"{base_name}.txt"
            download_mime = "text/plain"
            st.success(f"✅ 纯文本生成成功 ({len(download_data)} 字节)")
        elif export_format == "Word (.docx)":
            try:
                download_data = _md_to_docx(st.session_state.report)
                download_filename = f"{base_name}.docx"
                download_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                st.success(f"✅ Word文档生成成功 ({len(download_data)} 字节)")
            except Exception as e:
                st.error(f"Word导出失败: {e}")
                download_data = st.session_state.report.encode("utf-8")
                download_filename = f"{base_name}.md"
                download_mime = "text/markdown"
        elif export_format == "PDF (.pdf)":
            try:
                download_data = _md_to_pdf(st.session_state.report)
                download_filename = f"{base_name}.pdf"
                download_mime = "application/pdf"
                st.success(f"✅ PDF生成成功 ({len(download_data)} 字节)")
            except Exception as e:
                st.error(f"PDF导出失败: {e}")
                download_data = st.session_state.report.encode("utf-8")
                download_filename = f"{base_name}.md"
                download_mime = "text/markdown"
        else:
            download_data = st.session_state.report.encode("utf-8")
            download_filename = f"{base_name}.md"
            download_mime = "text/markdown"

        st.download_button(
            label=f"📥 下载 {export_format.split('(')[0].strip()}",
            data=download_data,
            file_name=download_filename,
            mime=download_mime,
            use_container_width=True,
        )

else:
    # Initial state - no scan yet
    st.info("👈 请在左侧设置中输入工作目录，然后点击 **🔍 扫描文件** 开始")

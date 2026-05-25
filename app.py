"""周报终结者 V1 - Streamlit Web界面."""

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


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

if "report" not in st.session_state:
    st.session_state.report = None
if "files" not in st.session_state:
    st.session_state.files = None
if "scan_done" not in st.session_state:
    st.session_state.scan_done = False


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

    # -- Model selection --
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

    st.divider()

    # -- Usage tips --
    st.markdown("### 💡 使用提示")
    st.markdown(
        "1. 输入工作目录路径\n"
        "2. 选择扫描天数\n"
        "3. 选择AI模型\n"
        "4. 点击 **🚀 生成周报**\n"
        "5. 等待分析完成\n"
        "6. 下载生成的周报"
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

    # -- Generate button --
    if total_files > 0 and selected_provider_key:
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

    elif total_files > 0 and not selected_provider_key:
        st.warning("请先在 `.env` 文件中配置API Key，然后重启应用")

    # -- Report preview & download --
    if st.session_state.report:
        st.divider()
        st.markdown("### 📋 生成的周报")
        st.markdown(st.session_state.report)

        st.divider()
        week_range = get_week_range()
        filename = f"周报_{week_range.replace(' ', '').replace('-', '_')}.md"

        st.download_button(
            label="📥 下载周报",
            data=st.session_state.report.encode("utf-8"),
            file_name=filename,
            mime="text/markdown",
            use_container_width=True,
        )

else:
    # Initial state - no scan yet
    st.info("👈 请在左侧设置中输入工作目录，然后点击 **🔍 扫描文件** 开始")

# X_WorkTrace

> **智能扫描工作文件，AI 自动分析内容变更，一键生成专业工作汇报**

基于 AI 的工作汇总工具。扫描你的工作目录，识别近期修改的文件，通过 AI 分析内容并自动生成结构化的工作周报。支持内容级对比、增量分析、周报归档、定时自动扫描，让周报撰写从繁琐变为轻松。

## 功能特性

### 文件扫描
- 自动识别 50+ 种文件类型（代码、文档、配置文件等）
- 支持 PDF 文件文本提取
- 支持 Excel（.xlsx/.xls）文件内容读取
- 支持 Word（.docx）文档解析
- 按时间范围筛选（最近 N 天）
- 自动跳过无关目录（node_modules、.git、__pycache__ 等）
- 多编码自动检测（UTF-8、GBK、GB2312、Latin-1）

### AI 分析
- 多模型支持：OpenAI、Claude、阿里百炼（通义千问）、自定义 OpenAI 兼容 API
- 内容级对比：对比文件具体变更，不只是文件是否修改
- 增量分析：只分析变更部分，避免重复汇报
- 并发处理：多线程同时分析多个文件（5 线程）
- 结果缓存：相同内容不重复分析，二次分析提速 90%+
- 敏感信息检测：自动识别 API Key、密码等敏感内容

### 报告生成
- 自动生成结构化工作周报
- 内置 3 种模板（标准、简洁、详细）
- 支持自定义模板上传（Word/PDF/Markdown）
- LLM 辅助模板结构分析
- 多格式导出：Markdown、Word、PDF、TXT

### 周报归档
- 每次生成周报后自动归档到本地 SQLite 数据库
- 同一天多次生成不会互相覆盖，分别保留
- 历史列表按时间倒序排列，支持查看完整详情
- 记录生成时间、日期范围、模板名称、来源文件统计
- 程序重启后数据不丢失
- 支持从归档中直接导出 Markdown/纯文本

### 历史快照
- 文件内容快照保存（用于增量对比）
- 变更追踪：新增/修改/删除文件识别
- 快照间对比
- 自动清理过期快照（可配置保留天数）

### 数据源扩展
- Git 提交记录
- 飞书聊天记录
- 钉钉
- 企业微信
- 邮件
- Google Calendar（预留）
- Jira（预留）
- Notion（预留）

### 自动化
- 每日定时自动扫描
- 后台自动生成报告并归档
- 可配置执行时间

### 界面设计
- 四页面布局：主页、模板、历史、设置
- iOS 风格毛玻璃 UI
- 流畅动画交互

## 快速开始

### 环境要求

- Python 3.9+
- 任意 LLM API Key（OpenAI / Claude / 百炼 / 自定义兼容 API）

### 安装

```bash
# 克隆项目
git clone https://github.com/lhvxhbz/week-report-agent.git
cd week-report-agent

# 安装依赖
pip install -r requirements.txt
```

### 配置

```bash
# 复制配置模板
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API 配置。以下是几种常见配置方式：

**使用阿里百炼（通义千问）：**
```env
LLM_PROVIDER=bailian
BAILIAN_API_KEY=sk-your-api-key
BAILIAN_MODEL=qwen-plus
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

**使用 OpenAI：**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

**使用自定义 OpenAI 兼容 API（如本地 Ollama、vLLM 等）：**
```env
LLM_PROVIDER=custom
CUSTOM_API_KEY=your-api-key
CUSTOM_MODEL=your-model-name
CUSTOM_BASE_URL=http://localhost:11434/v1
```

### 启动

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

## 使用指南

### 基本流程

1. 输入工作目录路径（你的项目/文档所在文件夹）
2. 选择扫描天数（默认 7 天）
3. 在设置页面配置 AI 模型（或使用 .env 配置）
4. 选择报告模板
5. 点击"生成工作汇总"
6. 等待 AI 分析完成
7. 预览周报内容，选择导出格式下载

### 内容级对比

开启此功能后，工具会：
- 读取文件的历史快照内容
- 逐行对比内容变更（unified diff）
- 统计新增/删除行数
- 只将变更部分发送给 AI 分析，减少 token 消耗

### 增量分析

结合历史快照，只分析：
- 新增的文件（完整分析）
- 内容有变更的文件（仅分析 diff）
- 跳过未修改的文件

### 周报归档

- 每次生成周报后自动归档保存
- 在"历史记录"页面查看所有已生成的周报
- 点击任意一条记录查看完整周报内容
- 支持从归档中重新导出

### 每日自动扫描

在设置页面：
1. 开启"每日自动扫描"
2. 设置执行时间（时:分）
3. 工具会在指定时间自动执行扫描、分析和报告生成
4. 生成的报告自动归档

### 模板使用

**内置模板：**
- 标准模板：适合日常周报
- 简洁模板：快速汇报要点
- 详细模板：项目级详细周报

**自定义模板：**
上传现有的周报文件（Word/PDF/Markdown），工具会自动提取结构作为模板，也可使用 LLM 辅助分析优化模板结构。

## 技术架构

### 项目结构

```
week-report-agent/
├── app.py                    # Streamlit 主界面
├── config.py                 # 配置管理（环境变量加载）
├── requirements.txt          # Python 依赖列表
├── .env.example              # 环境变量配置模板
├── core/
│   ├── file_reader.py        # 文件扫描和多格式读取
│   ├── analyzer.py           # AI 内容分析（并发+缓存+重试）
│   ├── generator.py          # 周报生成（模板+增量）
│   ├── diff_extractor.py     # 文件内容差异提取
│   ├── history.py            # 文件快照管理（JSON 存储）
│   ├── report_archive.py     # 周报归档管理（SQLite 存储）
│   ├── scheduler.py          # 定时任务调度
│   ├── template_manager.py   # 模板管理（内置+自定义+LLM分析）
│   ├── data_source.py        # 数据源抽象基类
│   ├── sensitivity.py        # 敏感信息检测
│   └── sources/              # 数据源实现
│       ├── git_source.py     # Git 提交记录
│       ├── feishu_source.py  # 飞书文档
│       ├── feishu_chat_source.py  # 飞书聊天
│       ├── dingtalk_source.py     # 钉钉
│       ├── wechat_work_source.py  # 企业微信
│       ├── email_source.py        # 邮件
│       ├── google_calendar_source.py  # Google Calendar
│       ├── jira_source.py    # Jira
│       └── notion_source.py  # Notion
├── llm/
│   ├── base.py               # LLMProvider 抽象基类
│   ├── openai_provider.py    # OpenAI 实现
│   ├── claude_provider.py    # Claude 实现
│   ├── bailian_provider.py   # 阿里百炼实现
│   ├── custom_provider.py    # 自定义 OpenAI 兼容 API 实现
│   └── factory.py            # Provider 工厂（自动检测+创建）
├── templates/
│   ├── builtin/              # 内置模板（standard/concise/detailed）
│   └── custom/               # 用户自定义模板目录
├── prompts/
│   ├── analyze.txt           # 文件分析提示词模板
│   └── generate.txt          # 周报生成提示词模板
└── .history/                 # 本地数据存储（自动创建，已 gitignore）
    ├── snapshots.json        # 文件快照数据
    └── report_archive.db    # 周报归档数据库（SQLite）
```

### 技术栈

| 组件 | 技术 |
|------|------|
| 前端框架 | Streamlit |
| UI 样式 | 自定义 CSS（iOS 毛玻璃风格） |
| AI 接口 | OpenAI API / Claude API / 百炼 API / 自定义兼容 API |
| 文档处理 | python-docx、PyPDF2、openpyxl |
| 并发处理 | ThreadPoolExecutor |
| 定时任务 | schedule |
| 数据存储 | SQLite（周报归档）+ JSON（文件快照） |
| 配置管理 | python-dotenv |

### 性能优化

| 优化项 | 说明 |
|--------|------|
| 并发文件读取 | 4 线程并发读取文件内容 |
| 并发 AI 分析 | 5 线程并发调用 LLM |
| 编码缓存 | 记住文件编码，避免重复检测 |
| 分析结果缓存 | 基于文件哈希缓存，未修改文件不重复分析 |
| 增量分析 | 只分析变更部分，减少 90%+ 的 token 消耗 |
| 自动重试 | 限流/网络错误自动重试（最多 3 次） |
| 错误率监控 | 实时统计分析成功率 |

## 更新日志

### V2.1 (2026-05-29)

**新增功能：**
- 周报历史归档：每次生成周报自动归档到本地 SQLite 数据库
- 归档详情查看：点击历史记录查看完整周报内容、元信息、来源文件
- 同一天多次生成分别保留，不互相覆盖
- 归档支持导出 Markdown/纯文本
- 归档支持删除管理

### V2.0 (2026-05-29)

**新增功能：**
- 内容级对比：对比文件具体变更内容
- 增量分析：只分析变更部分，避免重复汇报
- 每日自动扫描：定时自动执行扫描和报告生成
- 多格式支持：新增 PDF 和 Excel 文件读取
- 智能导航：主页/模板/历史/设置四页面布局
- 敏感信息检测：自动识别 API Key、密码等

**优化：**
- 代码精简和重构
- 移除冗余功能

### V1.0 (2026-05-26)

- 初始版本发布
- 多模型 LLM 支持
- 多格式导出（Markdown/Word/PDF/TXT）
- iOS 风格 UI 设计
- 并发性能优化
- 历史快照功能
- 模板系统

## 贡献

欢迎提交 Issue 和 Pull Request。

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'Add your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 提交 Pull Request

## 许可证

MIT License

## 作者

[@lhvxhbz](https://github.com/lhvxhbz)

## 致谢

- [Streamlit](https://streamlit.io/)
- [OpenAI](https://openai.com/)
- [Anthropic](https://www.anthropic.com/)
- [阿里云百炼](https://bailian.console.aliyun.com/)
- [python-docx](https://python-docx.readthedocs.io/)
- [PyPDF2](https://pypi.org/project/PyPDF2/)
- [openpyxl](https://pypi.org/project/openpyxl/)

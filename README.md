# 📋 周报终结者

> **智能扫描工作文件，AI自动分析内容变更，一键生成专业工作汇报**

一个基于AI的工作汇总工具。扫描你的工作目录，识别近期修改的文件，通过AI分析内容并自动生成结构化的工作周报。支持内容级对比、增量分析、定时自动扫描，让周报撰写从繁琐变为轻松。

## 功能特性

### 文件扫描
- 自动识别50+种文件类型（代码、文档、配置文件等）
- 支持PDF文件文本提取
- 支持Excel文件内容读取
- 支持Word文档解析
- 按时间范围筛选（最近N天）

### AI分析
- 多模型支持：OpenAI、Claude、百炼、自定义API
- 内容级对比：对比文件具体变更，不只是文件是否修改
- 增量分析：只分析变更部分，避免重复汇报
- 并发处理：多线程同时分析多个文件
- 结果缓存：相同内容不重复分析

### 报告生成
- 自动生成结构化工作周报
- 内置3种模板（标准、简洁、详细）
- 支持自定义模板上传
- 多格式导出：Markdown、Word、PDF、TXT

### 历史管理
- 文件快照保存
- 变更追踪对比
- 历史报告查看

### 自动化
- 每日定时自动扫描
- 后台自动生成报告
- 可配置执行时间

### 界面设计
- 四页面布局：主页、模板、历史、设置
- iOS风格毛玻璃UI
- 流畅动画交互

## 快速开始

### 环境要求

- Python 3.9+
- 任意LLM API Key（OpenAI/Claude/百炼或自定义）

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

编辑 `.env` 文件，填入你的API配置：

```env
# 选择模型提供商：openai / claude / bailian / custom
LLM_PROVIDER=custom

# 自定义API配置（当LLM_PROVIDER=custom时）
CUSTOM_API_KEY=your-api-key
CUSTOM_MODEL=your-model-name
CUSTOM_BASE_URL=https://your-api-endpoint.com/v1
```

### 启动

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

## 使用指南

### 基本流程

1. 输入工作目录路径
2. 选择扫描天数（默认7天）
3. 选择AI模型和模板
4. 点击"生成工作汇总"
5. 等待AI分析完成
6. 选择导出格式下载报告

### 内容级对比

开启此功能后，工具会：
- 读取文件的历史快照
- 逐行对比内容变更
- 统计新增/删除行数
- 只将变更部分发送给AI分析

### 增量分析

结合历史快照，只分析：
- 新增的文件
- 内容有变更的文件
- 跳过未修改的文件

### 每日自动扫描

在设置页面：
1. 开启"每日自动扫描"
2. 设置执行时间（时:分）
3. 工具会在指定时间自动执行扫描和报告生成

### 模板使用

**内置模板：**
- 标准模板：适合日常周报
- 简洁模板：快速汇报要点
- 详细模板：项目级详细周报

**自定义模板：**
上传现有的周报文件，工具会自动提取结构作为模板。

## 技术架构

### 项目结构

```
week-report-agent/
├── app.py                  # Streamlit主界面
├── config.py               # 配置管理
├── requirements.txt        # 依赖列表
├── .env.example            # 环境变量模板
├── core/
│   ├── file_reader.py      # 文件扫描和读取
│   ├── analyzer.py         # AI内容分析
│   ├── generator.py        # 周报生成
│   ├── history.py          # 历史快照管理
│   ├── diff_extractor.py   # 内容差异提取
│   ├── scheduler.py        # 定时任务调度
│   └── template_manager.py # 模板管理
├── llm/
│   ├── base.py             # LLMProvider基类
│   ├── openai_provider.py  # OpenAI实现
│   ├── claude_provider.py  # Claude实现
│   ├── bailian_provider.py # 百炼实现
│   ├── custom_provider.py  # 自定义API实现
│   └── factory.py          # 提供商工厂
├── templates/
│   ├── builtin/            # 内置模板
│   └── custom/             # 自定义模板目录
└── prompts/
    ├── analyze.txt         # 文件分析提示词
    └── generate.txt        # 周报生成提示词
```

### 技术栈

| 组件 | 技术 |
|------|------|
| 前端框架 | Streamlit |
| UI样式 | 自定义CSS（iOS风格） |
| AI接口 | OpenAI API / Claude API / 百炼 API |
| 文档处理 | python-docx、PyPDF2、openpyxl |
| 并发处理 | ThreadPoolExecutor |
| 定时任务 | schedule |
| 数据存储 | JSON快照文件 |

### 性能优化

| 优化项 | 效果 |
|--------|------|
| 并发文件读取 | 4线程并发 |
| 并发AI分析 | 5线程并发 |
| 编码缓存 | 避免重复检测 |
| 结果缓存 | 二次分析提速90%+ |
| 增量分析 | 减少90%+分析量 |

## 更新日志

### V2.0 (2026-05-29)

**新增功能：**
- 内容级对比：对比文件具体变更内容
- 增量分析：只分析变更部分，避免重复汇报
- 每日自动扫描：定时自动执行扫描和报告生成
- 多格式支持：新增PDF和Excel文件读取
- 智能导航：主页/模板/历史/设置四页面布局

**优化：**
- 代码精简和重构
- 移除冗余功能

### V1.0 (2026-05-26)

- 初始版本发布
- 多模型LLM支持
- 多格式导出（Markdown/Word/PDF/TXT）
- iOS风格UI设计
- 并发性能优化
- 历史快照功能
- 模板系统

## 贡献

欢迎提交Issue和Pull Request。

1. Fork本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'Add your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 提交Pull Request

## 许可证

MIT License

## 作者

[@lhvxhbz](https://github.com/lhvxhbz)

## 致谢

- [Streamlit](https://streamlit.io/)
- [OpenAI](https://openai.com/)
- [python-docx](https://python-docx.readthedocs.io/)
- [PyPDF2](https://pypi.org/project/PyPDF2/)
- [openpyxl](https://pypi.org/project/openpyxl/)

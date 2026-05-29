# 📋 周报终结者 V2.0 - AI驱动的工作汇总工具

> **一句话描述**：智能扫描工作文件，AI自动分析内容变更，生成专业的增量工作汇报

## ✨ V2.0 核心特性

### 🆕 V2.0 新增功能
- 🔄 **内容级对比** - 对比文件具体变更，不只是文件是否修改
- 📊 **增量分析** - 只分析变更部分，避免重复汇报
- 🕐 **每日自动扫描** - 定时自动扫描并生成报告
- 📄 **多格式支持** - 新增PDF和Excel文件读取
- 🎯 **智能导航** - 主页/模板/历史/设置四页面布局

### 📁 核心功能
- 🔍 **智能文件扫描** - 自动识别近期修改的工作文件（50+文件类型）
- 🤖 **AI内容分析** - 多模型支持（OpenAI/Claude/百炼/自定义）
- 📊 **结构化生成** - 自动生成专业的工作汇总
- 📥 **多格式导出** - 支持Markdown/Word/PDF/TXT
- 💾 **历史快照** - 保存文件快照，支持变更追踪

### ⚡ 亮点功能
- 🚀 **并发处理** - 多线程文件读取和AI分析
- 💾 **结果缓存** - 避免重复分析，提升效率
- 📄 **模板系统** - 内置3种模板，支持自定义
- 🎨 **iOS风格UI** - 毛玻璃材质、流畅动画

## 🚀 快速开始

### 环境要求
- Python 3.9+
- 任意LLM API Key

### 安装步骤
```bash
# 克隆项目
git clone https://github.com/lhvxhbz/week-report-agent.git
cd week-report-agent

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的API Key

# 启动应用
streamlit run app.py
```

### 配置说明
```env
# 选择模型提供商
LLM_PROVIDER=custom

# 自定义API配置
CUSTOM_API_KEY=your-api-key
CUSTOM_MODEL=your-model-name
CUSTOM_BASE_URL=https://your-api-endpoint.com/v1
```

## 📖 使用指南

### 基本流程
1. **输入工作目录** - 选择要扫描的文件夹路径
2. **选择扫描天数** - 设置扫描最近N天的文件（默认7天）
3. **配置AI模型** - 选择或配置AI模型
4. **生成工作汇总** - 点击按钮，AI自动分析并生成报告
5. **导出报告** - 选择格式（Markdown/Word/PDF/TXT）并下载

### V2.0 新功能详解

#### 🔄 内容级对比
- 对比文件具体内容变更，不只是文件是否修改
- 显示新增/删除的行数统计
- 只分析变更部分，减少重复汇报

#### 🕐 每日自动扫描
- 在设置页面开启自动扫描功能
- 设置每天执行时间（精确到分钟）
- 后台自动执行扫描和报告生成

#### 📄 多格式支持
- **文本文件**：50+种格式（.py, .js, .ts, .html, .css, .json, .md, .txt等）
- **Word文档**：.docx格式
- **PDF文件**：.pdf格式（文本提取）
- **Excel文件**：.xlsx, .xls格式

### 模板选择
- **标准模板** - 适合日常周报
- **简洁模板** - 快速汇报
- **详细模板** - 项目周报

### 自定义模板
支持上传现有的周报文件，自动提取模板结构

## 🏗️ 技术架构

### 项目结构
```
week-report-agent/
├── app.py                  # Streamlit主界面（4089行）
├── config.py               # 配置管理
├── core/
│   ├── file_reader.py      # 文件扫描模块（支持PDF/Excel）
│   ├── analyzer.py         # 内容分析模块（支持增量分析）
│   ├── generator.py        # 周报生成模块（支持增量报告）
│   ├── history.py          # 历史记录模块（快照管理）
│   ├── diff_extractor.py   # 内容差异提取模块
│   ├── scheduler.py        # 定时任务调度器
│   └── template_manager.py # 模板管理模块
├── llm/
│   ├── base.py             # LLMProvider基类
│   ├── openai_provider.py  # OpenAI实现
│   ├── claude_provider.py  # Claude实现
│   ├── bailian_provider.py # 百炼实现
│   ├── custom_provider.py  # 自定义API
│   └── factory.py          # 提供商工厂
├── templates/              # 模板系统
│   ├── builtin/            # 内置模板
│   └── custom/             # 自定义模板
└── prompts/                # Prompt模板
    ├── analyze.txt         # 文件分析提示词
    └── generate.txt        # 周报生成提示词
```

### 技术栈
- **前端**：Streamlit + 自定义CSS（iOS风格）
- **后端**：Python 3.9+
- **AI**：OpenAI/Claude/百炼 API
- **文档处理**：python-docx, PyPDF2, openpyxl
- **定时任务**：schedule库

### 核心设计
- **LLM适配层**：统一接口，支持多模型切换
- **并发处理**：ThreadPoolExecutor多线程优化
- **缓存机制**：基于文件哈希的结果缓存
- **增量分析**：对比历史快照，只分析变更部分
- **模板系统**：JSON格式模板，支持导入导出

## 📊 性能优化

| 优化项 | 效果 |
|--------|------|
| 并发文件读取 | 4线程并发，提升4倍 |
| 并发AI分析 | 5线程并发，提升5倍 |
| 编码缓存 | 避免重复检测 |
| 结果缓存 | 二次分析提速90%+ |
| 增量分析 | 只分析变更部分，减少90%+分析量 |

## 🎯 适用场景

- 👨‍💼 **职场人士** - 每周工作汇报
- 👩‍💻 **开发者** - 项目进展总结
- 📊 **产品经理** - 工作成果整理
- 🎓 **学生** - 学习周报
- 📝 **自由职业者** - 工作记录和汇报

## 📝 更新日志

### V2.0 (2026-05-29)
- 🔄 内容级对比 - 对比文件具体变更，不只是文件是否修改
- 📊 增量分析 - 只分析变更部分，避免重复汇报
- 🕐 每日自动扫描 - 定时自动扫描并生成报告
- 📄 多格式支持 - 新增PDF和Excel文件读取
- 🎯 智能导航 - 主页/模板/历史/设置四页面布局
- 🧹 代码优化 - 精简代码，移除冗余功能

### V1.0 (2026-05-26)
- ✨ 初始版本发布
- 🤖 支持多模型LLM
- 📄 支持多格式导出
- 🎨 iOS风格UI设计
- ⚡ 并发性能优化

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 👨‍💻 作者

- GitHub: [@lhvxhbz](https://github.com/lhvxhbz)

## 🙏 致谢

- [Streamlit](https://streamlit.io/) - Web框架
- [OpenAI](https://openai.com/) - AI模型
- [python-docx](https://python-docx.readthedocs.io/) - Word文档处理
- [PyPDF2](https://pypi.org/project/PyPDF2/) - PDF文档处理
- [openpyxl](https://pypi.org/project/openpyxl/) - Excel文档处理

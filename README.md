# 周报终结者 V1

> 每周五下午的痛苦，终于结束了。

## 这是什么

周报终结者是一个AI驱动的周报自动生成工具。它会扫描你最近修改过的工作文件，用AI分析每个文件的内容和改动，然后自动生成一份结构清晰的周报。

不用再对着空白文档发呆了。

## 解决什么问题

- 每周花1-2小时写周报，内容还经常遗漏
- 改了10个文件，只记得3个
- 写出来的周报像流水账，没有重点
- 临时拼凑，质量不稳定

## 核心功能

- **智能扫描**：自动扫描最近N天内修改过的文件
- **AI分析**：逐个分析文件，提取工作内容和改动
- **一键生成**：把分析结果整合成结构化周报
- **直接下载**：生成Markdown文件，复制粘贴即可

## 支持的文件格式

| 类型 | 格式 |
|------|------|
| 文档 | .txt, .md, .docx, .pdf |
| 代码 | .py, .js, .ts, .tsx, .jsx, .html, .css, .java, .go, .rs |
| 配置 | .json, .yaml, .yml, .toml, .ini, .cfg |
| 脚本 | .sh, .bat, .ps1, .sql |
| 其他 | .csv, .xml, .svg, .log |

单个文件大小限制：1MB

## 支持的AI模型

| 提供商 | 默认模型 | 说明 |
|--------|----------|------|
| OpenAI | gpt-4o-mini | 推荐，性价比高 |
| Claude | claude-3-5-sonnet | 质量最好，价格较高 |
| 阿里百炼 | qwen-turbo | 国内访问快，价格便宜 |
| 自定义 | - | 兼容OpenAI格式的任何API |

## 安装步骤

### 1. 下载项目

```bash
git clone https://github.com/your-username/week-report-agent.git
cd week-report-agent
```

或者直接下载ZIP文件解压。

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

依赖列表：
- streamlit（Web界面）
- openai（OpenAI/Claude API）
- anthropic（Claude专用）
- python-docx（读取Word文档）
- python-dotenv（加载环境变量）

### 3. 配置API Key

复制配置模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的API Key（见下方详细说明）。

### 4. 启动应用

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

## 配置说明

### .env 文件配置

打开 `.env` 文件，你会看到这样的结构：

```bash
# 选择使用的模型提供商：openai, claude, bailian, custom
LLM_PROVIDER=openai

# OpenAI 配置
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1

# Claude 配置
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# 阿里百炼配置
BAILIAN_API_KEY=sk-your-bailian-api-key
BAILIAN_MODEL=qwen-turbo
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 自定义API配置
CUSTOM_API_KEY=your-custom-api-key
CUSTOM_MODEL=your-model-name
CUSTOM_BASE_URL=https://your-api-endpoint.com/v1
```

### API Key 获取方式

#### OpenAI
1. 访问 https://platform.openai.com/api-keys
2. 注册/登录账号
3. 点击 "Create new secret key"
4. 复制生成的 `sk-` 开头的密钥

#### Claude (Anthropic)
1. 访问 https://console.anthropic.com/
2. 注册/登录账号
3. 进入 "API Keys" 页面
4. 点击 "Create Key"
5. 复制生成的 `sk-ant-` 开头的密钥

#### 阿里百炼 (DashScope)
1. 访问 https://dashscope.console.aliyun.com/
2. 用阿里云账号登录
3. 开通百炼服务
4. 在 "API-KEY管理" 中创建密钥
5. 复制生成的密钥

#### 自定义API
如果你有其他兼容OpenAI格式的API（比如本地部署的模型），填写：
- `CUSTOM_API_KEY`：你的API密钥
- `CUSTOM_MODEL`：模型名称
- `CUSTOM_BASE_URL`：API地址（必须兼容OpenAI格式）

### 可选配置项

```bash
# 扫描的文件扩展名（逗号分隔）
FILE_EXTENSIONS=.txt,.md,.docx,.pdf

# LLM生成参数
MAX_TOKENS=4096
TEMPERATURE=0.7
```

## 使用方法

### 基本流程

1. **启动应用**
   ```bash
   streamlit run app.py
   ```

2. **输入工作目录**
   在左侧边栏输入你要扫描的文件夹路径（绝对路径或相对路径）

3. **设置扫描天数**
   拖动滑块选择扫描最近几天的文件（默认7天）

4. **选择AI模型**
   系统会自动检测已配置API Key的模型，从下拉框选择

5. **扫描文件**
   点击 "🔍 扫描文件" 按钮，等待扫描完成

6. **生成周报**
   确认文件列表无误后，点击 "🚀 生成周报" 按钮

7. **下载周报**
   生成完成后，点击 "📥 下载周报" 保存为Markdown文件

### 界面说明

- **左侧边栏**：所有配置选项
- **统计卡片**：显示扫描到的文件数量、时间范围、总大小
- **文件列表**：可展开查看具体扫描到哪些文件
- **进度条**：显示AI分析文件的进度
- **预览区**：直接在页面上预览生成的周报

## 技术架构

```
week-report-agent/
├── app.py              # Streamlit Web界面
├── config.py           # 配置管理（读取.env）
├── requirements.txt    # Python依赖
├── .env.example        # 配置模板
├── core/
│   ├── file_reader.py  # 文件扫描和读取
│   ├── analyzer.py     # 文件内容分析（调用LLM）
│   └── generator.py    # 周报生成（调用LLM）
├── llm/
│   ├── base.py         # LLM提供商基类
│   ├── openai_provider.py
│   ├── claude_provider.py
│   ├── bailian_provider.py
│   ├── custom_provider.py
│   └── factory.py      # 提供商工厂
└── prompts/
    ├── analyze.txt     # 文件分析提示词
    └── generate.txt    # 周报生成提示词
```

工作流程：
1. `file_reader.py` 扫描指定目录，找出最近修改的文件
2. `analyzer.py` 逐个调用LLM分析文件内容
3. `generator.py` 把所有分析结果整合，调用LLM生成周报
4. `app.py` 提供Web界面，串联整个流程

## 常见问题

### Q: 扫描不到文件怎么办？

A: 检查以下几点：
- 路径是否正确（建议用绝对路径）
- 文件是否在最近N天内修改过
- 文件大小是否超过1MB
- 文件格式是否受支持

### Q: 生成的周报质量不好怎么办？

A: 可以尝试：
- 换一个更强的模型（比如gpt-4o或claude-3-5-sonnet）
- 调整扫描天数，覆盖更多工作内容
- 确保工作文件有足够的内容

### Q: API调用失败怎么办？

A: 常见原因：
- API Key 填写错误（检查是否有空格）
- 账户余额不足
- 网络问题（国内访问OpenAI可能需要代理）
- 模型名称填写错误

### Q: 支持PDF文件吗？

A: 目前支持读取PDF文件内容，但依赖系统安装的PDF解析工具。如果遇到问题，建议把PDF内容复制到txt或md文件中。

### Q: 文件内容会泄露吗？

A: 文件内容会发送到你配置的AI提供商的服务器进行分析。如果你使用的是OpenAI/Claude等商业服务，请注意：
- 不要扫描包含敏感信息的文件
- 可以配置只扫描特定目录
- 考虑使用本地部署的模型（通过自定义API配置）

## 注意事项

### API 费用

使用本工具会产生API调用费用，具体取决于：
- 扫描文件数量（每个文件调用一次API分析）
- 选择的模型（不同模型价格不同）
- 文件内容长度（影响token消耗）

大致费用参考（扫描10个普通文件）：
- OpenAI gpt-4o-mini：约 ¥0.1-0.3
- Claude 3.5 Sonnet：约 ¥0.5-1.0
- 阿里百炼 qwen-turbo：约 ¥0.05-0.1

### 文件大小限制

单个文件最大1MB。超过限制的文件会被自动跳过。

### 扫描深度

默认最多递归扫描5层目录。不会扫描隐藏目录（如.git、.vscode）和常见的依赖目录（如node_modules、venv）。

### 隐私说明

- 文件内容仅用于AI分析，不会被存储
- 不会收集任何个人信息
- API调用记录取决于你使用的AI提供商的政策

## 许可证

MIT License

## 问题反馈

如果遇到问题或有建议，欢迎提交Issue。

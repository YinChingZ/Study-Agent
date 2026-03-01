<div align="center">

[English](README.md) | [简体中文](README_zh-CN.md)

</div>

# 📚 StudyAgent — 自动做题 Agent


基于 [browser-use](https://github.com/browser-use/browser-use) 构建的通用自动做题 Agent。通过 CDP 连接本地 Chrome 浏览器，采用**双 Agent 架构**（Browser Agent + Solver Agent），将浏览器操作与解题推理分离，显著提升做题准确率。

## ✨ 功能特性

- **双 Agent 架构**：Browser Agent 操作页面，Solver Agent 专注解题推理，职责清晰
- **多题型支持**：选择题、填空题、判断题、简答题
- **独立模型配置**：可为浏览器操作和解题推理分配不同模型（如轻量模型导航 + 强模型解题）
- **自动翻页**：完成当前页后自动翻到下一页继续
- **自动提交**：所有题目完成后自动点击提交
- **思维链输出**：Solver Agent 展示完整的推理过程
- **操作可视化**：Demo 模式高亮 Agent 正在操作的元素
- **模块化架构**：清晰的包结构，支持编程调用与自定义扩展

## 🆕 本次会话新增内容（Web UI）

- 新增 **FastAPI Web UI 模式**：控制台、设置页、回顾页、WebSocket 实时推送。
- 新增 **YAML 优先配置**（`config.yaml`），并保留 `.env` 回退兼容。
- 新增 **Chrome 自动启动与 CDP 有效性探测**，启动报错更明确。
- 新增 **SQLite 做题历史存储**（`sessions` + `questions`）。
- 新增 **登录等待流程**：输入 URL 后先打开页面并暂停，手动登录后点击“恢复”再执行。
- 新增 **控制台状态持久化**：切到设置/回顾页面再回来不会丢失核心信息。
- 设置页升级为 **Browser Agent / Solver Agent 分开配置**，并修复“保存其他配置导致 API Key 被清空”问题。

## 🧭 运行模式

### CLI 模式（保持原行为）

```bash
python main.py
```

### Web UI 模式

```bash
python main.py --web
# 可选
python main.py --web --host 127.0.0.1 --port 7860
```

浏览器访问 `http://127.0.0.1:7860`。

## 📁 项目结构

```
Study-Agent/
├── main.py                    # 入口（CLI / Web）
├── config.example.yaml        # 演示配置模板
├── study_agent/               # 核心包
│   ├── __init__.py            # 公开 API 导出
│   ├── config.py              # 配置数据类 & 环境变量加载
│   ├── prompts.py             # 所有提示词模板
│   ├── llm_factory.py         # LLM 工厂（OpenAI / Anthropic / Google）
│   ├── browser.py             # BrowserSession 创建与管理
│   ├── event_bus.py           # 运行时事件总线
│   ├── chrome_manager.py      # Chrome 检测/启动/CDP 探测
│   ├── app.py                 # StudyAgentApp — 主编排器
│   ├── store/
│   │   └── history.py         # SQLite 历史存储
│   ├── web/
│   │   ├── server.py          # FastAPI 入口
│   │   ├── api/               # 配置/任务/回顾 API
│   │   ├── ws/                # WebSocket 事件推送
│   │   ├── templates/         # Jinja2 页面
│   │   └── static/            # CSS/JS
│   └── tools/
│       ├── __init__.py
│       └── solver.py          # solve_question 工具 & 答案解析
├── requirements.txt
└── .env                       # API Key 与配置
```

## 📋 前置要求

- Python 3.11+
- Chrome 浏览器（或 Chromium 内核浏览器）
- OpenAI、Anthropic 或 Google API Key

## 🚀 快速开始

### 1. 安装依赖

```bash
cd Study-Agent
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置 API Key

编辑 `.env` 文件，推荐使用以下配置结构（支持 OpenAI, Anthropic, Google）：

```env
# 全局默认提供商 (openai / anthropic / google)
DEFAULT_PROVIDER=openai

# OpenAI 配置
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

# Google 配置
GOOGLE_API_KEY=your-gemini-key
# GOOGLE_MODEL=gemini-2.0-flash

# Anthropic 配置
ANTHROPIC_API_KEY=sk-ant-key
```

**双 Agent 独立模型配置**（可选，可混合使用不同厂商的模型）：

```env
# 浏览器操作使用 OpenAI
BROWSER_PROVIDER=openai
BROWSER_MODEL=gpt-4o-mini

# 解题推理使用 Google Gemini
SOLVER_PROVIDER=google
SOLVER_MODEL=gemini-2.0-flash
```

Web UI 也可使用 YAML 配置：

```bash
cp config.example.yaml config.yaml
```

`config.yaml` 已加入忽略，不会提交到仓库；请使用 `config.example.yaml` 分享示例。

### 3. 启动 Chrome Debug 模式

必须以远程调试端口启动 Chrome，Agent 才能连接：

**Windows：**
```cmd
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug-profile"
```

**macOS：**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug-profile"
```

**Linux：**
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug-profile"
```

> 💡 **验证**：打开浏览器访问 `http://localhost:9222/json/version`，如果看到 JSON 信息则说明 debug 端口正常。

### 4. 导航到题目页面

在刚才打开的 Chrome 中：
1. 手动登录目标学习/考试网站
2. 导航到题目页面（确保题目已加载完毕）

### 5. 运行 Agent

```bash
python main.py
```

Agent 会自动：
1. 连接你的 Chrome 浏览器
2. 识别页面上的题目
3. 逐题分析并作答
4. 翻页继续（如有下一页）
5. 最终提交答案

## ⚙️ 配置选项

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `DEFAULT_PROVIDER` | `openai` | 默认模型提供商：`openai`, `anthropic`, `google` |
| `BROWSER_PROVIDER` | — | Browser Agent 提供商 (覆盖默认值) |
| `SOLVER_PROVIDER` | — | Solver Agent 提供商 (覆盖默认值) |
| `OPENAI_API_KEY` | — | OpenAI API Key |
| `OPENAI_BASE_URL` | — | OpenAI API 地址 |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI 默认模型名称 |
| `GOOGLE_API_KEY` | — | Google (Gemini) API Key |
| `GOOGLE_MODEL` | `gemini-2.0-flash` | Google 默认模型名称 |
| `ANTHROPIC_API_KEY` | — | Anthropic API Key |
| `ANTHROPIC_MODEL` | `claude-3-5-sonnet` | Anthropic 模型名称 |
| `BROWSER_MODEL` | — | 指定 Browser Agent 使用的模型名称 |
| `SOLVER_MODEL` | — | 指定 Solver Agent 使用的模型名称 |
| `CDP_URL` | `http://localhost:9222` | Chrome DevTools Protocol 地址 |
| `BROWSER_USE_LOGGING_LEVEL` | `info` | 日志级别：`debug` / `info` / `warning` |

## 🔧 工作原理

### 双 Agent 架构

```
┌──────────────────────────────────────────────────────────────┐
│  StudyAgent（双 Agent 架构）                                  │
│                                                              │
│  ┌─────────────────────────┐   ┌──────────────────────────┐  │
│  │  Browser Agent          │   │  Solver Agent            │  │
│  │  (浏览器操作 LLM)        │   │  (解题推理 LLM)           │  │
│  │                         │   │                          │  │
│  │  · 截图理解，识别题目    │──>│  · 接收纯文本题目         │  │
│  │  · DOM 元素定位          │   │  · 专注深度推理           │  │
│  │  · 调用 solve_question  │   │  · 无浏览器上下文干扰     │  │
│  │  · 填入答案、点击选项    │<──│  · 返回答案 + 推理过程    │  │
│  │  · 翻页、提交            │   │                          │  │
│  └────────────┬────────────┘   └──────────────────────────┘  │
│               │                                              │
│  ┌────────────▼────────────┐                                 │
│  │  browser-use 框架       │                                 │
│  │  · 截图 → 分析 → 操作   │                                 │
│  │  · DOM 交互引擎          │                                 │
│  └────────────┬────────────┘                                 │
│               │ CDP                                          │
│  ┌────────────▼────────────┐                                 │
│  │  Chrome 浏览器           │                                 │
│  │  (用户已打开的实例)      │                                 │
│  └─────────────────────────┘                                 │
└──────────────────────────────────────────────────────────────┘
```

### 为什么要分离？

| 问题 | 单 Agent | 双 Agent |
|------|---------|----------|
| LLM 上下文 | 被 DOM、操作历史、截图等信息污染 | Solver 只看到纯题目文本 |
| 推理深度 | thinking 字段兼顾页面分析+解题 | Solver 全部认知预算用于解题 |
| 模型灵活性 | 只能用一个模型 | 轻量模型导航 + 强模型解题 |
| 答案质量 | 操作和推理相互干扰 | 各司其职，质量更高 |

## 🔌 编程接口

StudyAgent 支持作为库在你的代码中调用：

```python
import asyncio
from study_agent import StudyAgentApp, load_config

async def main():
    # 从环境变量加载配置
    cfg = load_config()

    # 自定义设置
    cfg.agent.max_steps = 50
    cfg.agent.demo_mode = False

    # 创建并运行
    app = StudyAgentApp(config=cfg)
    await app.run(task="只做选择题")

asyncio.run(main())
```

**核心类：**

| 类名 | 说明 |
|------|------|
| `StudyAgentApp` | 主应用类，编排完整的做题流程 |
| `AppConfig` | 顶层配置，聚合所有子配置 |
| `LLMConfig` | LLM 提供商/模型/接口地址配置 |
| `BrowserConfig` | CDP 连接参数 |
| `AgentConfig` | Agent 运行时参数（max_steps、vision 等） |

## ❓ 常见问题

### 无法连接 Chrome

- 确认 Chrome 已以 `--remote-debugging-port=9222` 参数启动
- 确认没有其他进程占用 9222 端口
- 访问 `http://localhost:9222/json/version` 验证

### Agent 做题不准确

- 尝试更换更强的模型（如 `gpt-4o` → `gpt-4.1`）
- 确保页面完全加载后再运行 Agent
- 检查页面是否有遮挡元素（弹窗、广告等）

### 按 Ctrl+C 后 Chrome 关闭了

- `kill()` 方法只是断开 CDP 连接，不会关闭浏览器
- 如果 Chrome 关闭了，可能是使用了临时 user-data-dir，重新启动时指定固定目录即可

## 📝 注意事项

- 本工具仅用于辅助学习，请遵守相关平台的使用规则
- Agent 的作答准确率取决于所用 LLM 模型的能力
- 建议在正式使用前先在练习题上测试效果

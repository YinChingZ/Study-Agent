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

## 📋 前置要求

- Python 3.11+
- Chrome 浏览器（或 Chromium 内核浏览器）
- OpenAI API Key 或 Anthropic API Key

## 🚀 快速开始

### 1. 安装依赖

```bash
cd Study-Agent
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置 API Key

编辑 `.env` 文件，填写你的 API Key：

```env
MODEL_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key-here
```

如果使用兼容 OpenAI API 的第三方服务，可同时设置：

```env
OPENAI_BASE_URL=https://your-api-provider.com/v1
OPENAI_MODEL=your-model-name
```

**双 Agent 独立模型配置**（可选，不设置则两者均使用 OPENAI_MODEL）：

```env
# 轻量模型负责浏览器操作，强模型负责解题
BROWSER_MODEL=gpt-4o-mini
SOLVER_MODEL=gpt-4o
```

如使用 Anthropic：

```env
MODEL_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

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
| `MODEL_PROVIDER` | `openai` | 模型提供商：`openai` 或 `anthropic` |
| `OPENAI_API_KEY` | — | OpenAI API Key |
| `OPENAI_BASE_URL` | — | OpenAI API 地址（用于兼容第三方服务） |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI 默认模型名称 |
| `BROWSER_MODEL` | — | Browser Agent 模型（不设置则用 OPENAI_MODEL） |
| `SOLVER_MODEL` | — | Solver Agent 模型（不设置则用 OPENAI_MODEL） |
| `ANTHROPIC_API_KEY` | — | Anthropic API Key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Anthropic 模型名称 |
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

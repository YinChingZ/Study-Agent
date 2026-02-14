<div align="center">

[English](README.md) | [简体中文](README_zh-CN.md)

</div>

# 📚 StudyAgent — Automated Question Answering Agent

A general-purpose automated question-answering agent built on [browser-use](https://github.com/browser-use/browser-use). It connects to a local Chrome browser via CDP and employs a **Dual Agent Architecture** (Browser Agent + Solver Agent) to separate browser operations from problem-solving reasoning, significantly improving accuracy.

## ✨ Features

- **Dual Agent Architecture**: The Browser Agent handles page interaction, while the Solver Agent focuses on reasoning, with clear separation of duties.
- **Multi-Question Type Support**: Multiple choice, fill-in-the-blank, true/false, and short answer questions.
- **Independent Model Configuration**: Assign different models for browser navigation and problem solving (e.g., a lightweight model for navigation + a powerful model for reasoning).
- **Auto Pagination**: Automatically navigates to the next page after completing the current one.
- **Auto Submission**: Automatically clicks submit after all questions are completed.
- **Chain of Thought**: The Solver Agent displays the complete reasoning process.
- **Visualized Operations**: Demo mode highlights the elements the Agent is interacting with.
- **Modular Architecture**: Clean package structure, supports programmatic invocation and custom extensions.

## 📁 Project Structure

```
Study-Agent/
├── main.py                    # Entry point (thin wrapper)
├── study_agent/               # Core package
│   ├── __init__.py            # Public API exports
│   ├── config.py              # Configuration dataclasses & env loading
│   ├── prompts.py             # All prompt templates
│   ├── llm_factory.py         # LLM factory (OpenAI / Anthropic / Google)
│   ├── browser.py             # BrowserSession creation & management
│   ├── app.py                 # StudyAgentApp — main orchestrator
│   └── tools/
│       ├── __init__.py
│       └── solver.py          # solve_question tool & answer parsing
├── requirements.txt
└── .env                       # API keys & configuration
```

##  Prerequisites

- Python 3.11+
- Chrome Browser (or Chromium-based browser)
- OpenAI, Anthropic, or Google API Key

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd Study-Agent
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure API Keys

Edit the `.env` file. We recommend the following configuration structure (supports OpenAI, Anthropic, Google):

```env
# Global Default Provider (openai / anthropic / google)
DEFAULT_PROVIDER=openai

# OpenAI Configuration
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

# Google Configuration
GOOGLE_API_KEY=your-gemini-key
# GOOGLE_MODEL=gemini-2.0-flash

# Anthropic Configuration
ANTHROPIC_API_KEY=sk-ant-key
```

**Dual Agent Independent Model Configuration** (Optional, allows mixing models from different providers):

```env
# Browser operation uses OpenAI
BROWSER_PROVIDER=openai
BROWSER_MODEL=gpt-4o-mini

# Reasoning uses Google Gemini
SOLVER_PROVIDER=google
SOLVER_MODEL=gemini-2.0-flash
```

### 3. Start Chrome in Debug Mode

Chrome must be started with the remote debugging port for the Agent to connect:

**Windows:**
```cmd
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug-profile"
```

**macOS:**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug-profile"
```

**Linux:**
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug-profile"
```

> 💡 **Verify**: Open `http://localhost:9222/json/version` in your browser. If you see JSON information, the debug port is working correctly.

### 4. Navigate to the Question Page

In the Chrome instance you just opened:
1. Manually log in to the target learning/exam website.
2. Navigate to the question page (ensure questions are fully loaded).

### 5. Run the Agent

```bash
python main.py
```

The Agent will automatically:
1. Connect to your Chrome browser.
2. Identify questions on the page.
3. Analyze and answer each question.
4. Turn pages (if there is a next page).
5. Submit the answers.

## ⚙️ Configuration Options

| Environment Variable | Default | Description |
|----------------------|---------|-------------|
| `DEFAULT_PROVIDER` | `openai` | Default model provider: `openai`, `anthropic`, `google` |
| `BROWSER_PROVIDER` | — | Browser Agent provider (overrides default) |
| `SOLVER_PROVIDER` | — | Solver Agent provider (overrides default) |
| `OPENAI_API_KEY` | — | OpenAI API Key |
| `OPENAI_BASE_URL` | — | OpenAI API Address |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI default model name |
| `GOOGLE_API_KEY` | — | Google (Gemini) API Key |
| `GOOGLE_MODEL` | `gemini-2.0-flash` | Google default model name |
| `ANTHROPIC_API_KEY` | — | Anthropic API Key |
| `ANTHROPIC_MODEL` | `claude-3-5-sonnet` | Anthropic model name |
| `BROWSER_MODEL` | — | Specific model name for Browser Agent |
| `SOLVER_MODEL` | — | Specific model name for Solver Agent |
| `CDP_URL` | `http://localhost:9222` | Chrome DevTools Protocol URL |
| `BROWSER_USE_LOGGING_LEVEL` | `info` | Logging level: `debug` / `info` / `warning` |

## 🔧 How it Works

### Dual Agent Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  StudyAgent (Dual Agent Architecture)                        │
│                                                              │
│  ┌─────────────────────────┐   ┌──────────────────────────┐  │
│  │  Browser Agent          │   │  Solver Agent            │  │
│  │  (Browser Ops LLM)      │   │  (Reasoning LLM)         │  │
│  │                         │   │                          │  │
│  │  · Visual analysis       │──>│  · Receives pure text     │  │
│  │  · DOM element locating  │   │  · Focus on reasoning     │  │
│  │  · Calls solve_question  │   │  · No context noise       │  │
│  │  · Inputs answers        │<──│  · Returns answer + CoT   │  │
│  │  · Pagination/Submit     │   │                          │  │
│  └────────────┬────────────┘   └──────────────────────────┘  │
│               │                                              │
│  ┌────────────▼────────────┐                                 │
│  │  browser-use Framework  │                                 │
│  │  · Screenshot -> Action │                                 │
│  │  · DOM Interaction Engine│                                 │
│  └────────────┬────────────┘                                 │
│               │ CDP                                          │
│  ┌────────────▼────────────┐                                 │
│  │  Chrome Browser         │                                 │
│  │  (User Instance)        │                                 │
│  └─────────────────────────┘                                 │
└──────────────────────────────────────────────────────────────┘
```

### Why Separate?

| Issue | Single Agent | Dual Agent |
|-------|--------------|------------|
| **LLM Context** | Polluted by DOM, history, screenshots, etc. | Solver sees only pure question text. |
| **Reasoning Depth** | Thinking budget split between UI analysis & solving. | Solver uses full cognitive budget for reasoning. |
| **Model Flexibility** | Locked to a single model. | Lightweight model for navigation + Powerful model for solving. |
| **Answer Quality** | Operations and reasoning interfere with each other. | Clear separation of duties leads to higher quality. |

## 🔌 Programmatic API

StudyAgent can be used as a library in your own code:

```python
import asyncio
from study_agent import StudyAgentApp, load_config

async def main():
    # Load config from environment variables
    cfg = load_config()

    # Customize settings
    cfg.agent.max_steps = 50
    cfg.agent.demo_mode = False

    # Create and run
    app = StudyAgentApp(config=cfg)
    await app.run(task="Answer only the multiple choice questions")

asyncio.run(main())
```

**Key classes:**

| Class | Description |
|-------|-------------|
| `StudyAgentApp` | Main application class, orchestrates the full workflow |
| `AppConfig` | Top-level config aggregating all sub-configs |
| `LLMConfig` | LLM provider/model/base_url configuration |
| `BrowserConfig` | CDP connection parameters |
| `AgentConfig` | Agent runtime parameters (max_steps, vision, etc.) |

## ❓ FAQ

### Cannot connect to Chrome

- Confirm Chrome was started with `--remote-debugging-port=9222`.
- Ensure no other process is using port 9222.
- Visit `http://localhost:9222/json/version` to verify.

### Agent answers are inaccurate

- Try using a stronger model (e.g., `gpt-4o` or `gemini-pro`).
- Ensure the page is fully loaded before running the Agent.
- Check for occluding elements (popups, ads).

### Chrome closes after Ctrl+C

- The `kill()` method only disconnects the CDP session, it does not close the browser.
- If Chrome closed, you might be using a temporary user-data-dir. Use a persistent directory to avoid this.

## 📝 Notes

- This tool is for educational assistance only. Please comply with the rules of the relevant platforms.
- The accuracy depends on the capabilities of the LLM model used.
- It is recommended to test on practice questions before formal use.

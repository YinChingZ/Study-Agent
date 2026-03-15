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

## 🆕 Session Updates (Web UI)

- Added **FastAPI Web UI mode** with dashboard, settings, review, and websocket live events.
- Added **YAML-first config** (`config.yaml`) with environment-variable fallback.
- Added **Chrome auto-launch + CDP validation** with clearer startup diagnostics.
- Added **task history persistence** via SQLite (`sessions` + `questions`).
- Added **login-wait flow**: input URL → open page → wait for manual login → click Resume.
- Added **dashboard state persistence** (logs/progress/screenshot/input cache) when switching pages.
- Added **separate Browser Agent / Solver Agent settings** and safer API key save behavior.

## 🧭 Modes

### CLI Mode (unchanged)

```bash
python main.py
```

### Web UI Mode

```bash
python main.py --web
# optional
python main.py --web --host 127.0.0.1 --port 7860
```

Then open `http://127.0.0.1:7860`.

## 📡 Status and Event Contract (Web UI)

### Task Status (`/api/task/status`)

- `idle`: no active task
- `running`: task is executing
- `paused`: task is paused (including login-wait)
- `stopped`: task was stopped (manual stop/interruption)
- `finished`: task completed normally
- `error`: task exited with error

### WebSocket Events (`/ws`)

- `task_started`: task started, fields: `task`, `cdp_url`, `task_url`
- `task_paused`: task paused, optional fields: `reason`, `url`
- `task_resumed`: task resumed, optional field: `reason`
- `task_stopped`: task stopped, optional field: `reason`
- `task_finished`: task finished, fields: `steps`, `final_result`
- `task_error`: task error, field: `error`
- `progress`: step progress, fields: `current`, `total`
- `question_found`: question detected, fields: `question`, `type`
- `solver_calling`: solver started reasoning
- `solver_answered`: solver returned answer, fields: `answer`, `reasoning`
- `screenshot`: on-demand screenshot, field: `image` (base64)
- `log`: log message, field: `message`

Note: UI status should be sourced from the status API. WebSocket events are used for real-time rendering and logs.

## 🛠️ Session Fix Summary (2026-03)

### Task Control and State Consistency

- Unified task status source: `idle/running/paused/stopped/finished/error` is now maintained by backend runtime state.
- Wired `pause/resume/stop` to real `browser-use.Agent` controls and stop checkpoints (`register_should_stop_callback`).
- Added frontend handling for `task_stopped` and status re-sync after WebSocket reconnect.
- Repeated Start clicks during running now return a friendly "already running" flow instead of a false failure.

### Progress and UI Semantics

- Backend now emits real step progress: `0/total` on start, `current/total` on each step, and final progress on completion.
- Dashboard copy now explicitly shows "step progress" to match event semantics.
- Preview panel renamed to on-demand question screenshot semantics to avoid false blank-screen expectations.

### History and Review Performance

- Session storage now separates `task_url` and `cdp_url`; review page shows the real task URL.
- Added DB index on `questions(session_id)` to speed up per-session question queries.
- History list API now supports `limit` + `offset` pagination.
- Session detail excludes screenshot payload by default; screenshot retrieval moved to a dedicated endpoint.
- Review page uses lazy screenshot loading and skips cache for running sessions.
- Added error handling on review fetch calls and localized datetime rendering in session list.

### Frontend Runtime Persistence Cleanup

- Runtime fields (logs, screenshot, elapsed time) are restored only for `running/paused` sessions.
- Runtime view state is cleared when status synchronizes to `idle` to prevent stale logs/timers.
- Static asset versioning was bumped to ensure browsers load the latest frontend code.

## 📁 Project Structure

```
Study-Agent/
├── main.py                    # Entry (CLI / Web)
├── config.example.yaml        # Demo config template
├── study_agent/               # Core package
│   ├── __init__.py            # Public API exports
│   ├── config.py              # Configuration dataclasses & env loading
│   ├── prompts.py             # All prompt templates
│   ├── llm_factory.py         # LLM factory (OpenAI / Anthropic / Google)
│   ├── browser.py             # BrowserSession creation & management
│   ├── event_bus.py           # Runtime event bus
│   ├── chrome_manager.py      # Chrome detect / launch / CDP probe
│   ├── app.py                 # StudyAgentApp — main orchestrator
│   ├── store/
│   │   └── history.py         # SQLite history store
│   ├── web/
│   │   ├── server.py          # FastAPI app entry
│   │   ├── api/               # config/task/review APIs
│   │   ├── ws/                # websocket event endpoint
│   │   ├── templates/         # Jinja2 pages
│   │   └── static/            # css/js
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

Or use YAML config for Web UI:

```bash
cp config.example.yaml config.yaml
```

`config.yaml` is intentionally git-ignored. Use `config.example.yaml` for sharing.

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

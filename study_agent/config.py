"""
StudyAgent 配置管理模块

负责：
  - 加载与验证环境变量
  - 提供全局配置常量与数据类
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
import yaml

# 加载 .env 文件
load_dotenv()

CONFIG_FILE = Path("config.yaml")


# ============================================================
# 数据类：LLM 配置
# ============================================================
@dataclass
class LLMConfig:
    """单个 LLM 的配置信息。"""
    provider: str  # openai / anthropic / google
    model: str | None = None
    base_url: str | None = None
    max_completion_tokens: int | None = None


@dataclass
class BrowserConfig:
    """浏览器连接配置。"""
    cdp_url: str = "http://localhost:9222"
    minimum_wait_page_load_time: float = 0.5
    wait_for_network_idle_page_load_time: float = 1.0
    wait_between_actions: float = 0.3
    auto_launch_chrome: bool = False
    cdp_port: int = 9222


@dataclass
class AgentConfig:
    """Agent 运行时配置。"""
    use_vision: bool = True
    use_thinking: bool = True
    max_actions_per_step: int = 3
    max_failures: int = 5
    max_steps: int = 200
    enable_planning: bool = True
    use_judge: bool = True
    demo_mode: bool = True


@dataclass
class AppConfig:
    """应用顶层配置，聚合所有子配置。"""
    browser_llm: LLMConfig = field(default_factory=lambda: LLMConfig(provider="openai"))
    solver_llm: LLMConfig = field(default_factory=lambda: LLMConfig(provider="openai"))
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    task_description: str = ""


# ============================================================
# 从环境变量构建配置
# ============================================================
def load_config() -> AppConfig:
    """从环境变量读取所有配置，返回 AppConfig 实例。"""
    default_provider = os.getenv("DEFAULT_PROVIDER", "openai").lower()

    # Browser LLM
    b_provider = os.getenv("BROWSER_PROVIDER", default_provider).lower()
    b_model = os.getenv("BROWSER_MODEL", None)
    b_base_url = os.getenv("BROWSER_BASE_URL", None)

    # Solver LLM
    s_provider = os.getenv("SOLVER_PROVIDER", default_provider).lower()
    s_model = os.getenv("SOLVER_MODEL", None)
    s_base_url = os.getenv("SOLVER_BASE_URL", None)

    # Solver 若为 OpenAI，默认设置 max_completion_tokens
    s_max_tokens = 16384 if s_provider == "openai" else None

    # Browser 连接
    cdp_url = os.getenv("CDP_URL", "http://localhost:9222")

    return AppConfig(
        browser_llm=LLMConfig(
            provider=b_provider,
            model=b_model,
            base_url=b_base_url,
        ),
        solver_llm=LLMConfig(
            provider=s_provider,
            model=s_model,
            base_url=s_base_url,
            max_completion_tokens=s_max_tokens,
        ),
        browser=BrowserConfig(cdp_url=cdp_url),
    )


def _to_bool(value: object, default: bool = False) -> bool:
    """将配置值安全转换为布尔值。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _to_int(value: object, default: int) -> int:
    """将配置值安全转换为整数。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: object, default: float) -> float:
    """将配置值安全转换为浮点数。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_config_from_yaml(path: Path = CONFIG_FILE) -> AppConfig:
    """从 YAML 文件加载配置。文件不存在时回退到环境变量。"""
    if not path.exists():
        return load_config()

    with open(path, "r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    api_keys = raw.get("api_keys", {}) or {}
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        value = api_keys.get(key)
        if value:
            os.environ[key] = value

    browser_llm_raw = raw.get("browser_llm", {}) or {}
    solver_llm_raw = raw.get("solver_llm", {}) or {}
    browser_raw = raw.get("browser", {}) or {}
    agent_raw = raw.get("agent", {}) or {}

    default_provider = str(
        browser_llm_raw.get("provider")
        or solver_llm_raw.get("provider")
        or os.getenv("DEFAULT_PROVIDER", "openai")
    ).lower()

    browser_provider = str(browser_llm_raw.get("provider") or default_provider).lower()
    solver_provider = str(solver_llm_raw.get("provider") or default_provider).lower()

    browser_model = browser_llm_raw.get("model")
    browser_base_url = browser_llm_raw.get("base_url") or None
    solver_model = solver_llm_raw.get("model")
    solver_base_url = solver_llm_raw.get("base_url") or None

    # 兼容策略：若 Solver 与 Browser 使用同一 Provider，且 Solver 关键参数缺失，自动继承 Browser。
    if solver_provider == browser_provider:
        if not solver_base_url and browser_base_url:
            solver_base_url = browser_base_url
        if not solver_model and browser_model:
            solver_model = browser_model

    solver_max_tokens = (
        _to_int(solver_llm_raw.get("max_completion_tokens"), 16384)
        if solver_provider == "openai"
        else None
    )

    cdp_port = _to_int(browser_raw.get("cdp_port"), 9222)
    cdp_url = str(browser_raw.get("cdp_url") or f"http://localhost:{cdp_port}")

    return AppConfig(
        browser_llm=LLMConfig(
            provider=browser_provider,
            model=browser_model,
            base_url=browser_base_url,
            max_completion_tokens=(
                _to_int(browser_llm_raw.get("max_completion_tokens"), 0)
                if browser_llm_raw.get("max_completion_tokens") is not None
                else None
            ),
        ),
        solver_llm=LLMConfig(
            provider=solver_provider,
            model=solver_model,
            base_url=solver_base_url,
            max_completion_tokens=solver_max_tokens,
        ),
        browser=BrowserConfig(
            cdp_url=cdp_url,
            minimum_wait_page_load_time=_to_float(
                browser_raw.get("minimum_wait_page_load_time"),
                BrowserConfig.minimum_wait_page_load_time,
            ),
            wait_for_network_idle_page_load_time=_to_float(
                browser_raw.get("wait_for_network_idle_page_load_time"),
                BrowserConfig.wait_for_network_idle_page_load_time,
            ),
            wait_between_actions=_to_float(
                browser_raw.get("wait_between_actions"),
                BrowserConfig.wait_between_actions,
            ),
            auto_launch_chrome=_to_bool(browser_raw.get("auto_launch_chrome"), False),
            cdp_port=cdp_port,
        ),
        agent=AgentConfig(
            use_vision=_to_bool(agent_raw.get("use_vision"), AgentConfig.use_vision),
            use_thinking=_to_bool(agent_raw.get("use_thinking"), AgentConfig.use_thinking),
            max_actions_per_step=_to_int(
                agent_raw.get("max_actions_per_step"),
                AgentConfig.max_actions_per_step,
            ),
            max_failures=_to_int(agent_raw.get("max_failures"), AgentConfig.max_failures),
            max_steps=_to_int(agent_raw.get("max_steps"), AgentConfig.max_steps),
            enable_planning=_to_bool(agent_raw.get("enable_planning"), AgentConfig.enable_planning),
            use_judge=_to_bool(agent_raw.get("use_judge"), AgentConfig.use_judge),
            demo_mode=_to_bool(agent_raw.get("demo_mode"), AgentConfig.demo_mode),
        ),
        task_description=str(raw.get("task_description") or ""),
    )


def save_config_to_yaml(
    config: AppConfig,
    api_keys: dict[str, str],
    path: Path = CONFIG_FILE,
) -> None:
    """将配置序列化为 YAML 文件。"""
    data = {
        "api_keys": {
            "OPENAI_API_KEY": api_keys.get("OPENAI_API_KEY", ""),
            "ANTHROPIC_API_KEY": api_keys.get("ANTHROPIC_API_KEY", ""),
            "GOOGLE_API_KEY": api_keys.get("GOOGLE_API_KEY", ""),
        },
        "browser_llm": {
            "provider": config.browser_llm.provider,
            "model": config.browser_llm.model or "",
            "base_url": config.browser_llm.base_url or "",
            "max_completion_tokens": config.browser_llm.max_completion_tokens,
        },
        "solver_llm": {
            "provider": config.solver_llm.provider,
            "model": config.solver_llm.model or "",
            "base_url": config.solver_llm.base_url or "",
            "max_completion_tokens": config.solver_llm.max_completion_tokens,
        },
        "browser": {
            "cdp_url": config.browser.cdp_url,
            "auto_launch_chrome": config.browser.auto_launch_chrome,
            "cdp_port": config.browser.cdp_port,
            "minimum_wait_page_load_time": config.browser.minimum_wait_page_load_time,
            "wait_for_network_idle_page_load_time": config.browser.wait_for_network_idle_page_load_time,
            "wait_between_actions": config.browser.wait_between_actions,
        },
        "agent": {
            "use_vision": config.agent.use_vision,
            "use_thinking": config.agent.use_thinking,
            "max_actions_per_step": config.agent.max_actions_per_step,
            "max_failures": config.agent.max_failures,
            "max_steps": config.agent.max_steps,
            "enable_planning": config.agent.enable_planning,
            "use_judge": config.agent.use_judge,
            "demo_mode": config.agent.demo_mode,
        },
        "task_description": config.task_description,
    }

    with open(path, "w", encoding="utf-8") as file:
        yaml.dump(data, file, allow_unicode=True, default_flow_style=False, sort_keys=False)


def validate_config(config: AppConfig) -> None:
    """检查配置中所需的 API Key 是否已设置，缺失则退出。"""
    active_providers = {config.browser_llm.provider, config.solver_llm.provider}
    missing_keys: list[str] = []

    if "openai" in active_providers and not os.getenv("OPENAI_API_KEY"):
        missing_keys.append("OPENAI_API_KEY")
    if "anthropic" in active_providers and not os.getenv("ANTHROPIC_API_KEY"):
        missing_keys.append("ANTHROPIC_API_KEY")
    if "google" in active_providers and not os.getenv("GOOGLE_API_KEY"):
        missing_keys.append("GOOGLE_API_KEY")

    if missing_keys:
        print("❌ 错误：缺少环境变量：")
        for key in missing_keys:
            print(f"   - {key}")
        sys.exit(1)

"""
StudyAgent 配置管理模块

负责：
  - 加载与验证环境变量
  - 提供全局配置常量与数据类
"""

import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


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

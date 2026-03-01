"""配置管理 API。"""

import logging
from dataclasses import asdict
from pathlib import Path

import yaml

from fastapi import APIRouter
from pydantic import BaseModel, Field
from browser_use.llm.messages import UserMessage

from study_agent.chrome_manager import ChromeManager
from study_agent.config import (
    AgentConfig,
    AppConfig,
    BrowserConfig,
    LLMConfig,
    load_config_from_yaml,
    save_config_to_yaml,
)
from study_agent.llm_factory import create_llm

logger = logging.getLogger("study_agent.web")
router = APIRouter()


def _load_existing_api_keys() -> dict[str, str]:
    """读取已保存的 API Key（用于空值保存时保留原值）。"""
    config_path = Path("config.yaml")
    if not config_path.exists():
        return {
            "OPENAI_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "GOOGLE_API_KEY": "",
        }

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {
            "OPENAI_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "GOOGLE_API_KEY": "",
        }

    keys = raw.get("api_keys", {}) or {}
    return {
        "OPENAI_API_KEY": keys.get("OPENAI_API_KEY", ""),
        "ANTHROPIC_API_KEY": keys.get("ANTHROPIC_API_KEY", ""),
        "GOOGLE_API_KEY": keys.get("GOOGLE_API_KEY", ""),
    }


class LLMInput(BaseModel):
    provider: str = "openai"
    model: str | None = None
    base_url: str | None = None
    max_completion_tokens: int | None = None


class BrowserInput(BaseModel):
    cdp_url: str = "http://localhost:9222"
    auto_launch_chrome: bool = True
    cdp_port: int = 9222
    minimum_wait_page_load_time: float = 0.5
    wait_for_network_idle_page_load_time: float = 1.0
    wait_between_actions: float = 0.3


class AgentInput(BaseModel):
    use_vision: bool = True
    use_thinking: bool = True
    max_actions_per_step: int = 3
    max_failures: int = 5
    max_steps: int = 200
    enable_planning: bool = True
    use_judge: bool = True
    demo_mode: bool = True


class ConfigSaveRequest(BaseModel):
    api_keys: dict[str, str] = Field(default_factory=dict)
    browser_llm: LLMInput
    solver_llm: LLMInput
    browser: BrowserInput
    agent: AgentInput
    task_description: str = ""


class ValidateRequest(BaseModel):
    provider: str
    model: str | None = None
    base_url: str | None = None
    api_key: str


@router.get("/api/config")
async def get_config() -> dict:
    """返回当前配置（API Key 脱敏）。"""
    config = load_config_from_yaml()
    api_keys = {
        "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "GOOGLE_API_KEY": "",
    }
    return {
        "api_keys": api_keys,
        "browser_llm": asdict(config.browser_llm),
        "solver_llm": asdict(config.solver_llm),
        "browser": asdict(config.browser),
        "agent": asdict(config.agent),
        "task_description": config.task_description,
    }


@router.post("/api/config")
async def save_config(payload: ConfigSaveRequest) -> dict:
    """保存配置到 YAML。"""
    existing_api_keys = _load_existing_api_keys()
    merged_api_keys: dict[str, str] = {}
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        incoming = (payload.api_keys.get(key) or "").strip()
        merged_api_keys[key] = incoming if incoming else existing_api_keys.get(key, "")

    browser_data = payload.browser_llm.model_dump()
    solver_data = payload.solver_llm.model_dump()

    if (solver_data.get("provider") or "").lower() == (browser_data.get("provider") or "").lower():
        if not solver_data.get("base_url") and browser_data.get("base_url"):
            solver_data["base_url"] = browser_data.get("base_url")
        if not solver_data.get("model") and browser_data.get("model"):
            solver_data["model"] = browser_data.get("model")

    config = AppConfig(
        browser_llm=LLMConfig(**browser_data),
        solver_llm=LLMConfig(**solver_data),
        browser=BrowserConfig(**payload.browser.model_dump()),
        agent=AgentConfig(**payload.agent.model_dump()),
        task_description=payload.task_description,
    )
    save_config_to_yaml(config, merged_api_keys)
    return {"ok": True, "message": "配置已保存"}


@router.post("/api/config/validate")
async def validate_config_api(payload: ValidateRequest) -> dict:
    """验证 API Key 是否可用。"""
    env_key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    key_name = env_key_map.get(payload.provider.lower())
    if not key_name:
        return {"ok": False, "message": "不支持的 provider"}

    import os

    os.environ[key_name] = payload.api_key
    try:
        llm = create_llm(
            LLMConfig(
                provider=payload.provider.lower(),
                model=payload.model,
                base_url=payload.base_url,
            )
        )
        await llm.ainvoke([
            UserMessage(content="请仅回复ok"),
        ])
        return {"ok": True, "message": "API Key 验证成功"}
    except Exception as exc:
        logger.warning("API Key 校验失败: %s", exc)
        return {"ok": False, "message": f"验证失败：{exc}"}


@router.get("/api/config/chrome")
async def detect_chrome() -> dict:
    """检测 Chrome 安装与调试端口状态。"""
    manager = ChromeManager()
    chrome_path = manager.find_chrome()
    running = await manager.is_running()
    return {
        "installed": bool(chrome_path),
        "running": running,
        "path": chrome_path,
    }

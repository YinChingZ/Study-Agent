"""
StudyAgent LLM 工厂模块

根据配置信息创建不同提供商的 LLM 实例。
"""

import logging
import os

from browser_use.llm import ChatOpenAI, ChatAnthropic
from browser_use.llm.google.chat import ChatGoogle
from browser_use.llm.base import BaseChatModel

from study_agent.config import LLMConfig, AppConfig

logger = logging.getLogger("study_agent")


def _create_openai_llm(config: LLMConfig) -> ChatOpenAI:
    """创建 OpenAI LLM 实例。

    当环境变量 OPENAI_NO_STRUCTURED_OUTPUT=true 时，禁用 json_schema 结构化输出，
    改为将 schema 注入系统提示词。适用于不支持 response_format: json_schema 的第三方 API。
    """
    model = config.model or os.getenv("OPENAI_MODEL", "gpt-4o")
    base_url = config.base_url or os.getenv("OPENAI_BASE_URL", None)

    kwargs: dict = {"model": model}
    if base_url:
        kwargs["base_url"] = base_url
    if config.max_completion_tokens is not None:
        kwargs["max_completion_tokens"] = config.max_completion_tokens

    # 兼容不支持 json_schema 结构化输出的第三方 API
    no_structured = os.getenv("OPENAI_NO_STRUCTURED_OUTPUT", "false").lower() in (
        "true", "1", "yes",
    )
    if no_structured:
        kwargs["dont_force_structured_output"] = True
        kwargs["add_schema_to_system_prompt"] = True
        logger.info("⚙️ 已禁用 json_schema 结构化输出，改为 schema-in-prompt 模式")

    return ChatOpenAI(**kwargs)


def _create_anthropic_llm(config: LLMConfig) -> ChatAnthropic:
    """创建 Anthropic LLM 实例。"""
    model = config.model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    return ChatAnthropic(model=model)


def _create_google_llm(config: LLMConfig) -> ChatGoogle:
    """创建 Google LLM 实例。"""
    model = config.model or os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")
    return ChatGoogle(model=model)


_FACTORY_MAP = {
    "openai": _create_openai_llm,
    "anthropic": _create_anthropic_llm,
    "google": _create_google_llm,
}


def create_llm(config: LLMConfig) -> BaseChatModel:
    """根据 LLMConfig 创建对应提供商的 LLM 实例。"""
    factory = _FACTORY_MAP.get(config.provider)
    if factory is None:
        raise ValueError(f"不支持的 Provider: {config.provider}")
    return factory(config)


def create_llm_pair(app_config: AppConfig) -> tuple[BaseChatModel, BaseChatModel]:
    """创建 Browser Agent LLM 和 Solver LLM，并打印配置信息。"""
    bc = app_config.browser_llm
    sc = app_config.solver_llm

    print(f'🤖 Browser Agent: {bc.provider.upper()} (Model: {bc.model or "Default"})')
    if bc.base_url:
        print(f"   API Base: {bc.base_url}")

    print(f'🧠 Solver Agent: {sc.provider.upper()} (Model: {sc.model or "Default"})')
    if sc.base_url:
        print(f"   API Base: {sc.base_url}")

    browser_llm = create_llm(bc)
    solver_llm = create_llm(sc)
    return browser_llm, solver_llm

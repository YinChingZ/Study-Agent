"""
StudyAgent — 基于 browser-use 的自动做题 Agent（双 Agent 架构）

通过 ``study_agent`` 包提供模块化接口：

    from study_agent import StudyAgentApp, run_app, load_config

快速运行::

    import asyncio
    from study_agent import run_app
    asyncio.run(run_app())
"""

import os
import sys

# 将 browser-use 库加入 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "browser-use"))

from study_agent.config import AppConfig, LLMConfig, BrowserConfig, AgentConfig, load_config, validate_config
from study_agent.app import StudyAgentApp, run_app

__all__ = [
    "StudyAgentApp",
    "run_app",
    "AppConfig",
    "LLMConfig",
    "BrowserConfig",
    "AgentConfig",
    "load_config",
    "validate_config",
]

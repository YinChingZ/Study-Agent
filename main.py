"""
StudyAgent — 基于 browser-use 的自动做题 Agent（双 Agent 架构）

入口文件。实际逻辑已模块化至 study_agent 包中。

使用前请确保：
1. Chrome 已以 --remote-debugging-port=9222 参数启动
2. 已在 .env 中配置好 API Key
3. 已手动登录目标网站并导航到题目页面
"""

import asyncio

from study_agent import run_app


if __name__ == "__main__":
    asyncio.run(run_app())

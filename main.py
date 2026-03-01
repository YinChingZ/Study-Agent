"""StudyAgent 入口 — 支持 CLI 和 Web UI 两种模式。"""

import argparse
import asyncio

from study_agent import run_app


def main() -> None:
    """程序入口。"""
    parser = argparse.ArgumentParser(description="StudyAgent — 自动做题 Agent")
    parser.add_argument("--web", action="store_true", help="启动 Web UI 模式")
    parser.add_argument("--host", default="127.0.0.1", help="Web UI 监听地址")
    parser.add_argument("--port", type=int, default=7860, help="Web UI 端口")
    args = parser.parse_args()

    if args.web:
        from study_agent.web.server import start_server

        asyncio.run(start_server(host=args.host, port=args.port))
    else:
        asyncio.run(run_app())


if __name__ == "__main__":
    main()

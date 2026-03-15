"""
StudyAgent 应用编排模块

将配置、LLM、浏览器、工具、Agent 组装为完整的运行流程。
提供 StudyAgentApp 类，支持外部程序以编程方式调用。
"""

import asyncio
import logging
from datetime import datetime

from browser_use import Agent, Tools

from study_agent.config import AppConfig, load_config_from_yaml, validate_config
from study_agent.prompts import BROWSER_AGENT_PROMPT, DEFAULT_TASK_DESCRIPTION
from study_agent.llm_factory import create_llm_pair
from study_agent.browser import create_browser_session
from study_agent.tools.solver import register_solver_tool
from study_agent.event_bus import EventBus, EventType
from study_agent.store.history import HistoryStore

logger = logging.getLogger("study_agent")


class StudyAgentApp:
    """StudyAgent 应用封装，可编程创建与运行。

    Usage::

        app = StudyAgentApp()          # 使用环境变量默认配置
        await app.run()

        # 或自定义配置
        cfg = load_config()
        cfg.agent.max_steps = 50
        app = StudyAgentApp(config=cfg)
        await app.run(task="只做选择题")
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        event_bus: EventBus | None = None,
        history_store: HistoryStore | None = None,
        task_url: str | None = None,
    ) -> None:
        self.config = config or load_config_from_yaml()
        self._event_bus = event_bus
        self._history_store = history_store
        self._browser_session = None
        self._agent: Agent | None = None
        self._is_paused = False
        self._is_stopped = False
        self._status: str = "idle"
        self._status_detail: str | None = None
        self._task_url = task_url
        self._session_id: int | None = None

    # ----------------------------------------------------------
    # 公开方法
    # ----------------------------------------------------------
    async def run(self, task: str | None = None) -> None:
        """执行完整的做题流程。

        Args:
            task: 自定义任务描述。为 None 时使用默认任务描述或 config 中的 task_description。
        """
        self._print_banner()
        self._is_stopped = False

        # 1. 验证环境变量
        validate_config(self.config)

        if self._history_store:
            self._session_id = await self._history_store.create_session(
                task_url=self._task_url,
                cdp_url=self.config.browser.cdp_url,
                start_time=datetime.now().isoformat(),
            )

        self._status = "running"
        self._status_detail = None
        await self._emit(
            EventType.TASK_STARTED,
            {
                "task": task or self.config.task_description or DEFAULT_TASK_DESCRIPTION,
                "cdp_url": self.config.browser.cdp_url,
                "task_url": self._task_url,
            },
        )

        # 2. 创建 LLM
        browser_llm, solver_llm = create_llm_pair(self.config)

        # 3. 注册 solver 工具
        tools = Tools()
        register_solver_tool(
            tools,
            solver_llm,
            event_bus=self._event_bus,
            history_store=self._history_store,
            session_id_getter=lambda: self._session_id,
        )
        print("🔧 已注册自定义工具：solve_question")

        # 4. 浏览器会话
        self._browser_session = create_browser_session(self.config.browser)

        # 5. 确定任务描述
        task_text = task or self.config.task_description or DEFAULT_TASK_DESCRIPTION

        try:
            # 6. 创建 Browser Agent
            ac = self.config.agent
            self._agent = Agent(
                task=task_text,
                llm=browser_llm,
                tools=tools,
                browser_session=self._browser_session,
                use_vision=ac.use_vision,
                use_thinking=ac.use_thinking,
                max_actions_per_step=ac.max_actions_per_step,
                max_failures=ac.max_failures,
                max_steps=ac.max_steps,
                enable_planning=ac.enable_planning,
                use_judge=ac.use_judge,
                extend_system_message=BROWSER_AGENT_PROMPT,
                demo_mode=ac.demo_mode,
                register_should_stop_callback=self._should_stop,
            )

            if self._is_paused:
                self._agent.pause()

            await self._emit(
                EventType.PROGRESS,
                {
                    "current": 0,
                    "total": ac.max_steps,
                },
            )

            async def _on_step_end(agent_instance: Agent) -> None:
                await self._emit(
                    EventType.PROGRESS,
                    {
                        "current": min(agent_instance.state.n_steps, ac.max_steps),
                        "total": ac.max_steps,
                    },
                )

            print()
            print("🚀 Agent 开始做题...")
            print("   架构：Browser Agent（操作页面）→ Solver Agent（解题推理）")
            print("   （按 Ctrl+C 可随时中止）")
            print()

            # 7. 运行
            result = await self._agent.run(max_steps=ac.max_steps, on_step_end=_on_step_end)

            # 8. 结果摘要
            self._print_result(result)
            if self._is_stopped:
                self._status = "stopped"
                self._status_detail = "stop_requested"
                await self._emit(EventType.TASK_STOPPED, {"reason": "stop_requested"})
                if self._history_store and self._session_id is not None:
                    await self._history_store.finish_session(
                        session_id=self._session_id,
                        end_time=datetime.now().isoformat(),
                        status="stopped",
                    )
            else:
                self._status = "finished"
                self._status_detail = None
                await self._emit(
                    EventType.TASK_FINISHED,
                    {
                        "steps": len(result.history) if result else 0,
                        "final_result": result.final_result() if result else "",
                    },
                )
                await self._emit(
                    EventType.PROGRESS,
                    {
                        "current": ac.max_steps,
                        "total": ac.max_steps,
                    },
                )
                if self._history_store and self._session_id is not None:
                    await self._history_store.finish_session(
                        session_id=self._session_id,
                        end_time=datetime.now().isoformat(),
                        status="finished",
                    )

        except KeyboardInterrupt:
            print("\n\n⏹️  用户中止，正在清理...")
            self._status = "stopped"
            self._status_detail = "keyboard_interrupt"
            await self._emit(EventType.TASK_STOPPED, {"reason": "keyboard_interrupt"})
            if self._history_store and self._session_id is not None:
                await self._history_store.finish_session(
                    session_id=self._session_id,
                    end_time=datetime.now().isoformat(),
                    status="stopped",
                )
        except Exception as e:
            if self._is_stopped:
                self._status = "stopped"
                self._status_detail = "stop_requested"
                await self._emit(EventType.TASK_STOPPED, {"reason": "stop_requested"})
                if self._history_store and self._session_id is not None:
                    await self._history_store.finish_session(
                        session_id=self._session_id,
                        end_time=datetime.now().isoformat(),
                        status="stopped",
                    )
                return

            self._status = "error"
            self._status_detail = str(e)
            self._handle_error(e)
            await self._emit(EventType.TASK_ERROR, {"error": str(e)})
            if self._history_store and self._session_id is not None:
                await self._history_store.finish_session(
                    session_id=self._session_id,
                    end_time=datetime.now().isoformat(),
                    status="error",
                )
            raise
        finally:
            self._agent = None
            await self.cleanup()

    async def cleanup(self) -> None:
        """断开浏览器连接（不会关闭用户的 Chrome）。"""
        if self._browser_session:
            print("🔌 断开浏览器连接...")
            await self._browser_session.kill()
            self._browser_session = None
            print("👋 已退出。")

    def pause(self) -> None:
        """暂停任务。"""
        self._is_paused = True
        self._status = "paused"
        self._status_detail = None
        if self._agent:
            self._agent.pause()

    def resume(self) -> None:
        """恢复任务。"""
        self._is_paused = False
        self._status = "running"
        self._status_detail = None
        if self._agent:
            self._agent.resume()

    def stop(self) -> None:
        """停止任务。"""
        self._is_stopped = True
        self._is_paused = False
        self._status = "stopped"
        self._status_detail = "stop_requested"
        if self._agent:
            self._agent.stop()

    def get_status(self) -> str:
        """返回统一任务状态。"""
        return self._status

    def get_status_detail(self) -> str | None:
        """返回状态细节（调试用途）。"""
        return self._status_detail

    async def _should_stop(self) -> bool:
        """提供给底层 Agent 的停止检查点。"""
        return self._is_stopped

    async def _emit(self, event_type: EventType, data: dict | None = None) -> None:
        """安全发布事件。"""
        if self._event_bus is None:
            return
        await self._event_bus.emit(event_type, data)

    # ----------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------
    @staticmethod
    def _print_banner() -> None:
        print("=" * 60)
        print("  📚 StudyAgent — 自动做题 Agent（双 Agent 架构）")
        print("=" * 60)
        print()

    @staticmethod
    def _print_result(result) -> None:
        print()
        print("=" * 60)
        print("  ✅ 做题完成！")
        print("=" * 60)
        if result:
            final = result.final_result()
            if final:
                print(f"📋 结果摘要：{final}")
            print(f"📊 总步骤数：{len(result.history)}")
            errors = result.errors()
            if errors:
                print(f"⚠️  遇到 {len(errors)} 个错误")

    @staticmethod
    def _handle_error(e: Exception) -> None:
        error_msg = str(e)
        if "connect" in error_msg.lower() or "cdp" in error_msg.lower():
            print("\n❌ 无法连接到 Chrome，请检查：")
            print("   1. Chrome 是否已以 debug 模式启动？")
            print('   2. 启动命令：chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\chrome-debug-profile"')
            print("   3. 验证方式：浏览器访问 http://localhost:9222/json/version")
        else:
            print(f"\n❌ 运行出错：{e}")


# ============================================================
# 便捷函数（供 main.py 直接调用）
# ============================================================
async def run_app(task: str | None = None, config: AppConfig | None = None) -> None:
    """一键运行 StudyAgent。"""
    app = StudyAgentApp(config=config)
    await app.run(task=task)

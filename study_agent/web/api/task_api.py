"""任务控制 API。"""

import asyncio
import json
import logging
import webbrowser
from urllib.parse import quote
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Request
from pydantic import BaseModel

from study_agent import StudyAgentApp
from study_agent.chrome_manager import ChromeManager
from study_agent.config import AppConfig
from study_agent.config import load_config_from_yaml
from study_agent.event_bus import EventType, event_bus
from study_agent.prompts import DEFAULT_TASK_DESCRIPTION

logger = logging.getLogger("study_agent.web")
router = APIRouter()


class StartTaskRequest(BaseModel):
    url: str | None = None
    task_description: str | None = None


async def _launch_agent_task(request: Request, config: AppConfig, task_text: str) -> None:
    """创建并后台运行 Agent。"""
    store = request.app.state.history_store
    agent_app = StudyAgentApp(config=config, event_bus=event_bus, history_store=store)
    request.app.state.agent_app = agent_app

    async def _runner() -> None:
        try:
            await agent_app.run(task=task_text)
        except Exception as exc:
            await event_bus.emit(EventType.TASK_ERROR, {"error": str(exc)})

    request.app.state.agent_task = asyncio.create_task(_runner())


def _open_url_for_login(cdp_url: str, target_url: str) -> bool:
    """通过 CDP 打开目标页面，失败时回退系统浏览器。"""
    cdp_base = cdp_url.rstrip("/")
    encoded = quote(target_url, safe="")
    new_tab_endpoint = f"{cdp_base}/json/new?{encoded}"

    try:
        with urlopen(UrlRequest(new_tab_endpoint, method="PUT"), timeout=3.0) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
            return bool(payload)
    except Exception:
        webbrowser.open(target_url)
        return False


@router.post("/api/task/start")
async def start_task(request: Request, body: StartTaskRequest) -> dict:
    """创建并启动任务。"""
    current_task = getattr(request.app.state, "agent_task", None)
    if current_task and not current_task.done():
        return {"status": "running", "message": "已有任务在运行"}

    config = load_config_from_yaml()

    chrome_manager = None
    if config.browser.auto_launch_chrome:
        try:
            chrome_manager = ChromeManager(port=config.browser.cdp_port)
            cdp_url = await chrome_manager.ensure_running()
            config.browser.cdp_url = cdp_url
            request.app.state.chrome_manager = chrome_manager
        except Exception as exc:
            error_text = f"Chrome 调试连接失败：{exc}"
            await event_bus.emit(EventType.TASK_ERROR, {"error": error_text})
            return {"status": "error", "message": error_text}

    request.app.state.pending_task_payload = None
    if current_task and current_task.done():
        request.app.state.agent_task = None

    task_text = body.task_description or config.task_description or DEFAULT_TASK_DESCRIPTION

    # 输入 URL 时，先打开页面并暂停，等待用户登录后手动恢复。
    if body.url:
        opened_by_cdp = _open_url_for_login(config.browser.cdp_url, body.url)
        request.app.state.agent_task = None
        request.app.state.pending_task_payload = {
            "config": config,
            "task_text": task_text,
            "url": body.url,
        }
        await event_bus.emit(
            EventType.TASK_PAUSED,
            {
                "reason": "waiting_login",
                "url": body.url,
            },
        )
        await event_bus.emit(
            EventType.LOG,
            {
                "message": (
                    "已打开任务页面，请先在浏览器完成登录，然后点击“恢复”继续。"
                    if opened_by_cdp
                    else "已尝试打开任务页面（CDP 打开失败已回退系统浏览器），请登录后点击“恢复”。"
                )
            },
        )
        return {
            "status": "paused",
            "message": "等待用户登录，点击“恢复”后开始执行",
            "waiting_login": True,
        }

    await _launch_agent_task(request, config, task_text)
    return {"status": "started", "waiting_login": False}


@router.post("/api/task/pause")
async def pause_task(request: Request) -> dict:
    """暂停当前任务。"""
    agent_app: StudyAgentApp | None = request.app.state.agent_app
    if not agent_app:
        return {"status": "idle", "message": "当前没有运行中的任务"}
    agent_app.pause()
    await event_bus.emit(EventType.TASK_PAUSED, {})
    return {"status": "paused"}


@router.post("/api/task/resume")
async def resume_task(request: Request) -> dict:
    """恢复当前任务。"""
    pending = getattr(request.app.state, "pending_task_payload", None)
    if pending:
        request.app.state.pending_task_payload = None
        await event_bus.emit(EventType.TASK_RESUMED, {"reason": "user_login_completed"})
        await _launch_agent_task(
            request,
            config=pending["config"],
            task_text=pending["task_text"],
        )
        return {"status": "running", "message": "已恢复并开始执行"}

    agent_app: StudyAgentApp | None = request.app.state.agent_app
    if not agent_app:
        return {"status": "idle", "message": "没有可恢复的任务，请先点击“开始”"}
    agent_app.resume()
    await event_bus.emit(EventType.TASK_RESUMED, {})
    return {"status": "running"}


@router.post("/api/task/stop")
async def stop_task(request: Request) -> dict:
    """停止当前任务。"""
    agent_app: StudyAgentApp | None = request.app.state.agent_app
    pending = getattr(request.app.state, "pending_task_payload", None)

    if pending:
        request.app.state.pending_task_payload = None
        await event_bus.emit(EventType.TASK_STOPPED, {"reason": "cancel_waiting_login"})
        return {"status": "stopped"}

    if not agent_app:
        return {"status": "idle", "message": "当前没有运行中的任务"}

    agent_app.stop()
    task: asyncio.Task | None = request.app.state.agent_task
    if task and not task.done():
        task.cancel()

    await event_bus.emit(EventType.TASK_STOPPED, {})
    return {"status": "stopped"}


@router.get("/api/task/status")
async def task_status(request: Request) -> dict:
    """获取任务状态。"""
    task: asyncio.Task | None = request.app.state.agent_task
    pending = getattr(request.app.state, "pending_task_payload", None)
    status: str
    if pending:
        status = "paused"
    elif task is None:
        status = "idle"
    elif task.done():
        status = "finished"
    else:
        status = "running"
    return {"status": status, "waiting_login": bool(pending)}

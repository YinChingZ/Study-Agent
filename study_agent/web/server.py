"""
Web UI 服务器入口。

职责：
- 挂载 API 路由和 WebSocket endpoint
- 提供 Jinja2 模板渲染页面
- 管理 StudyAgentApp 生命周期
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from study_agent.store.history import HistoryStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期。"""
    store = HistoryStore()
    await store.init()
    app.state.history_store = store
    app.state.agent_app = None
    app.state.agent_task = None
    app.state.chrome_manager = None
    app.state.pending_task_payload = None
    app.state.task_status = "idle"
    app.state.current_task_url = None
    yield
    if app.state.agent_app:
        await app.state.agent_app.cleanup()
    if app.state.chrome_manager:
        app.state.chrome_manager.shutdown()


app = FastAPI(title="StudyAgent", lifespan=lifespan)

base_dir = Path(__file__).parent
templates_dir = base_dir / "templates"
static_dir = base_dir / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

from study_agent.web.api.config_api import router as config_router
from study_agent.web.api.task_api import router as task_router
from study_agent.web.api.review_api import router as review_router
from study_agent.web.ws.events import router as ws_router

app.include_router(config_router)
app.include_router(task_router)
app.include_router(review_router)
app.include_router(ws_router)


@app.get("/")
async def index(request: Request):
    """控制台页面。"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/settings")
async def settings(request: Request):
    """配置页面。"""
    return templates.TemplateResponse("settings.html", {"request": request})


@app.get("/review")
async def review(request: Request):
    """回顾页面。"""
    return templates.TemplateResponse("review.html", {"request": request})


async def start_server(host: str = "127.0.0.1", port: int = 7860) -> None:
    """启动 Web 服务器并自动打开浏览器。"""
    import uvicorn
    import webbrowser

    webbrowser.open(f"http://{host}:{port}")
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

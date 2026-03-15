"""做题记录查询 API。"""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/api/history")
async def list_history(request: Request, limit: int = 50, offset: int = 0) -> dict:
    """获取历史会话列表。"""
    store = request.app.state.history_store
    sessions = await store.list_sessions(limit=limit, offset=offset)
    return {"items": sessions}


@router.get("/api/history/{session_id}")
async def session_detail(session_id: int, request: Request) -> dict:
    """获取会话详情和题目列表。"""
    store = request.app.state.history_store
    detail = await store.get_session_detail(session_id, include_screenshots=False)
    if not detail:
        raise HTTPException(status_code=404, detail="会话不存在")
    return detail


@router.get("/api/history/questions/{question_id}/screenshot")
async def question_screenshot(question_id: int, request: Request):
    store = request.app.state.history_store
    b64 = await store.get_question_screenshot(question_id)
    if b64 is None:
        raise HTTPException(status_code=404, detail="截图不存在")
    return {"screenshot_b64": b64}

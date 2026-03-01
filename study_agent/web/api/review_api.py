"""做题记录查询 API。"""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/api/history")
async def list_history(request: Request) -> dict:
    """获取历史会话列表。"""
    store = request.app.state.history_store
    sessions = await store.list_sessions()
    return {"items": sessions}


@router.get("/api/history/{session_id}")
async def session_detail(session_id: int, request: Request) -> dict:
    """获取会话详情和题目列表。"""
    store = request.app.state.history_store
    detail = await store.get_session_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="会话不存在")
    return detail

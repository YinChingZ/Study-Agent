"""
异步事件总线 — Agent 运行过程中的可观测性基础。

Agent 各环节 emit 事件，Web 层订阅后通过 WebSocket 推送给前端。
CLI 模式下无订阅者时，emit 操作为空（零开销）。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable

logger = logging.getLogger("study_agent.web")


# Web UI canonical task statuses.
TASK_STATUSES = ("idle", "running", "paused", "stopped", "finished", "error")


class EventType(str, Enum):
    """事件类型枚举。"""

    TASK_STARTED = "task_started"
    TASK_PAUSED = "task_paused"
    TASK_RESUMED = "task_resumed"
    TASK_STOPPED = "task_stopped"
    TASK_FINISHED = "task_finished"
    TASK_ERROR = "task_error"

    QUESTION_FOUND = "question_found"
    SOLVER_CALLING = "solver_calling"
    SOLVER_ANSWERED = "solver_answered"
    ANSWER_FILLED = "answer_filled"
    PAGE_TURNING = "page_turning"

    SCREENSHOT = "screenshot"
    LOG = "log"
    PROGRESS = "progress"


@dataclass
class Event:
    """事件对象。"""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


Subscriber = Callable[[Event], Awaitable[None]]


class EventBus:
    """进程内异步事件总线。线程安全，支持多订阅者。"""

    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []
        self._lock = asyncio.Lock()

    def subscribe(self, callback: Subscriber) -> Callable[[], None]:
        """订阅事件。返回取消订阅函数。"""
        self._subscribers.append(callback)

        def unsubscribe() -> None:
            try:
                self._subscribers.remove(callback)
            except ValueError:
                return

        return unsubscribe

    async def emit(self, event_type: EventType, data: dict[str, Any] | None = None) -> None:
        """发布事件。无订阅者时为空操作。"""
        if not self._subscribers:
            return

        event = Event(type=event_type, data=data or {})
        async with self._lock:
            subscribers = list(self._subscribers)

        results = await asyncio.gather(
            *(subscriber(event) for subscriber in subscribers),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.debug("事件订阅回调执行失败：%s", result)


event_bus = EventBus()

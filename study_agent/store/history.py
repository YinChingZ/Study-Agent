"""
做题记录持久化（SQLite）。

表结构：
- sessions: 每次运行一条记录
- questions: 每道题一条记录
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aiosqlite

DB_PATH = Path.home() / ".studyagent" / "history.db"


class HistoryStore:
    """做题历史记录存储。"""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    async def init(self) -> None:
        """初始化数据库与表结构。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    total_questions INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running'
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    question_type TEXT,
                    answer TEXT,
                    reasoning TEXT,
                    screenshot_b64 TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
                """
            )
            await conn.commit()

    async def create_session(self, url: str | None, start_time: str, status: str = "running") -> int:
        """创建新会话并返回会话 ID。"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "INSERT INTO sessions(url, start_time, status) VALUES (?, ?, ?)",
                (url, start_time, status),
            )
            await conn.commit()
            return int(cursor.lastrowid)

    async def add_question(
        self,
        session_id: int,
        question_text: str,
        question_type: str,
        answer: str,
        reasoning: str,
        screenshot_b64: str | None,
        created_at: str,
    ) -> int:
        """记录一道题并返回题目记录 ID。"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """
                INSERT INTO questions(
                    session_id, question_text, question_type, answer, reasoning, screenshot_b64, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, question_text, question_type, answer, reasoning, screenshot_b64, created_at),
            )
            await conn.execute(
                "UPDATE sessions SET total_questions = total_questions + 1 WHERE id = ?",
                (session_id,),
            )
            await conn.commit()
            return int(cursor.lastrowid)

    async def finish_session(self, session_id: int, end_time: str, status: str) -> None:
        """标记会话完成。"""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "UPDATE sessions SET end_time = ?, status = ? WHERE id = ?",
                (end_time, status, session_id),
            )
            await conn.commit()

    async def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """查询历史会话列表。"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT id, url, start_time, end_time, total_questions, status
                FROM sessions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_session_detail(self, session_id: int) -> dict[str, Any] | None:
        """获取会话详情及题目列表。"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            session_cursor = await conn.execute(
                """
                SELECT id, url, start_time, end_time, total_questions, status
                FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            )
            session = await session_cursor.fetchone()
            if not session:
                return None

            question_cursor = await conn.execute(
                """
                SELECT id, session_id, question_text, question_type, answer, reasoning, screenshot_b64, created_at
                FROM questions
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            )
            questions = await question_cursor.fetchall()

            data = dict(session)
            data["questions"] = [dict(row) for row in questions]
            return data

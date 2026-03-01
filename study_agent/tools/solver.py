"""
StudyAgent Solver Tool

定义 solve_question 自定义工具——调用独立的 Solver LLM 进行解题。
"""

import base64
import logging
from datetime import datetime
from typing import Callable

from pydantic import BaseModel, Field

from browser_use import ActionResult, Tools
from browser_use.browser import BrowserSession
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import (
    ContentPartImageParam,
    ContentPartTextParam,
    ImageURL,
    SystemMessage,
    UserMessage,
)

from study_agent.prompts import SOLVER_SYSTEM_PROMPT
from study_agent.event_bus import EventBus, EventType
from study_agent.store.history import HistoryStore

logger = logging.getLogger("study_agent")


# ============================================================
# 参数模型
# ============================================================
class SolveQuestionParams(BaseModel):
    """solve_question 工具的参数模型。"""

    question: str = Field(
        description='完整的题目内容，包括题干、选项（如有）、题目类型。'
                    '示例："【单选题】以下哪个是中国的首都？A. 上海  B. 北京  C. 广州  D. 深圳"'
    )
    question_type: str = Field(
        default="auto",
        description="题目类型：choice（选择题）、fill（填空题）、judge（判断题）、essay（简答题）、auto（自动识别）",
    )
    answer_format_hint: str = Field(
        default="",
        description='答案格式提示，从题目中提取的格式要求。'
                    '例如："round to the nearest hundredth"、"enter an exact value"、"as a fraction"、"to 2 decimal places"。'
                    '如果没有特殊格式要求，留空即可。',
    )
    include_screenshot: bool = Field(
        default=False,
        description="是否将当前页面截图一并发送给解题模型。"
                    "当题目包含图片、图表、几何图形、函数图像、化学结构式、电路图等视觉元素时设为 true。"
                    "纯文字题目保持 false 以节省资源。",
    )


# ============================================================
# 答案解析
# ============================================================
def parse_solver_response(answer_text: str) -> tuple[str, str]:
    """从 Solver 返回的文本中解析 ANSWER 和 REASONING 部分。

    Returns:
        (answer_part, reasoning_part)
    """
    answer_part = answer_text
    reasoning_part = ""
    if "ANSWER:" in answer_text:
        after_answer = answer_text.split("ANSWER:", 1)[-1]
        if "REASONING:" in after_answer:
            answer_part = after_answer.split("REASONING:", 1)[0].strip()
            reasoning_part = after_answer.split("REASONING:", 1)[1].strip()
        else:
            answer_part = after_answer.strip()
    return answer_part, reasoning_part


def truncate_reasoning(reasoning: str, question_type: str) -> str:
    """根据题目类型截断推理文本，避免返回内容过长。"""
    limits = {
        "choice": 200,
        "judge": 150,
        "fill": 300,
        "essay": 1500,
        "auto": 500,
    }
    max_len = limits.get(question_type, 500)
    if len(reasoning) <= max_len:
        return reasoning
    return reasoning[:max_len] + "...(推理已截断)"


# ============================================================
# 注册 solve_question 工具
# ============================================================
def register_solver_tool(
    tools: Tools,
    solver_llm: BaseChatModel,
    event_bus: EventBus | None = None,
    history_store: HistoryStore | None = None,
    session_id_getter: Callable[[], int | None] | None = None,
) -> None:
    """向 Tools 实例注册 solve_question 自定义工具。"""

    @tools.action(
        "Solve a question: send the complete question text to the solver AI and get the answer. "
        "You MUST use this tool for every question before filling in answers on the page. "
        "Include the full question text with all options. "
        "Set include_screenshot=true when the question contains images, charts, graphs, geometric figures, or other visual elements.",
        param_model=SolveQuestionParams,
    )
    async def solve_question(params: SolveQuestionParams, browser_session: BrowserSession) -> ActionResult:
        """调用 Solver LLM 解答题目，返回推理过程和答案。支持多模态（文本+截图）。"""
        logger.info(f"🧠 Solver 收到题目：{params.question[:80]}...")
        if event_bus:
            await event_bus.emit(
                EventType.QUESTION_FOUND,
                {
                    "question": params.question[:200],
                    "type": params.question_type,
                },
            )

        # ---- 按需截图 ----
        screenshot_b64: str | None = None
        if params.include_screenshot:
            try:
                screenshot_bytes = await browser_session.take_screenshot(full_page=False)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                logger.info(f"📸 已捕获页面截图（{len(screenshot_bytes)} bytes），将发送给 Solver")
                if event_bus:
                    await event_bus.emit(EventType.SCREENSHOT, {"image": screenshot_b64})
            except Exception as e:
                logger.warning(f"⚠️ 截图失败，将仅使用文本解题：{e}")

        # ---- 构建题目提示文本 ----
        type_hint = ""
        if params.question_type != "auto":
            type_map = {
                "choice": "这是一道选择题",
                "fill": "这是一道填空题",
                "judge": "这是一道判断题",
                "essay": "这是一道简答题/论述题",
            }
            type_hint = f"\n\n提示：{type_map.get(params.question_type, '')}"

        format_hint = ""
        if params.answer_format_hint:
            format_hint = f"\n\n答案格式要求：{params.answer_format_hint}"
        elif params.question_type == "fill":
            format_hint = "\n\n答案格式要求：请优先使用小数形式（保留两位小数），不要使用 LaTeX 或特殊符号。"

        user_text = f"请解答以下题目：\n\n{params.question}{type_hint}{format_hint}"

        # ---- 构建消息（支持多模态） ----
        if screenshot_b64:
            user_message = UserMessage(content=[
                ContentPartTextParam(text=user_text),
                ContentPartTextParam(text="\n以下是题目所在页面的截图，请结合截图中的视觉信息（图表、图形、公式等）进行解题："),
                ContentPartImageParam(
                    image_url=ImageURL(
                        url=f"data:image/png;base64,{screenshot_b64}",
                        media_type="image/png",
                        detail="high",
                    )
                ),
            ])
            logger.info("🖼️ 使用多模态消息（文本+截图）调用 Solver")
        else:
            user_message = UserMessage(content=user_text)

        messages = [
            SystemMessage(content=SOLVER_SYSTEM_PROMPT),
            user_message,
        ]

        if event_bus:
            await event_bus.emit(EventType.SOLVER_CALLING, {})

        # 调用独立的 Solver LLM
        response = await solver_llm.ainvoke(messages)
        answer_text = response.completion if isinstance(response.completion, str) else str(response.completion)

        logger.info(f"✅ Solver 返回答案 ({len(answer_text)} 字符)")

        # 解析答案
        answer_part, reasoning_part = parse_solver_response(answer_text)
        logger.info(f"✅ 解析答案：{answer_part}")

        # 截断推理
        truncated_reasoning = truncate_reasoning(reasoning_part, params.question_type)

        # 组装返回内容
        result_content = f"ANSWER: {answer_part}"
        if truncated_reasoning:
            result_content += f"\n\nREASONING: {truncated_reasoning}"

        if event_bus:
            await event_bus.emit(
                EventType.SOLVER_ANSWERED,
                {
                    "answer": answer_part,
                    "reasoning": truncated_reasoning,
                },
            )

        if history_store and session_id_getter:
            session_id = session_id_getter()
            if session_id is not None:
                await history_store.add_question(
                    session_id=session_id,
                    question_text=params.question,
                    question_type=params.question_type,
                    answer=answer_part,
                    reasoning=reasoning_part,
                    screenshot_b64=screenshot_b64,
                    created_at=datetime.now().isoformat(),
                )

        return ActionResult(
            extracted_content=f"题目答案：\n{result_content}",
            long_term_memory=f"题目：{params.question[:100]}... → 答案：{answer_part}",
        )

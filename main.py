"""
StudyAgent — 基于 browser-use 的自动做题 Agent（双 Agent 架构）

架构设计：
  - Browser Agent（浏览器操作 Agent）：负责页面导航、题目识别、元素定位与交互
  - Solver Agent（解题 Agent）：通过自定义 Tool 调用，专注于题目推理和答案生成

这种职责分离确保：
  1. 解题 LLM 的上下文不被 DOM/操作历史污染，全部认知预算用于推理
  2. 浏览器 Agent 专注于"看到题目 → 调 solver → 填入答案"的操作流
  3. 可为两个角色使用不同模型（如轻量模型导航 + 强模型解题）

使用前请确保：
1. Chrome 已以 --remote-debugging-port=9222 参数启动
2. 已在 .env 中配置好 API Key
3. 已手动登录目标网站并导航到题目页面
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 将 browser-use 库加入 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'browser-use'))

from pydantic import BaseModel, Field

from browser_use import Agent, ActionResult, Tools
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.llm import ChatOpenAI, ChatAnthropic
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import SystemMessage, UserMessage

logger = logging.getLogger('study_agent')

# ============================================================
# Solver Agent 的系统提示（纯解题，无浏览器操作指令）
# ============================================================
SOLVER_SYSTEM_PROMPT = """你是一个学业非常优秀的学生，擅长各个学科，包括但不限于数学、物理、化学、生物、英语、历史、地理、政治、计算机科学等。

你的唯一任务是：根据给出的题目内容，给出正确答案。

## 答题规则

### 选择题
- 仔细阅读题干和每个选项
- 注意否定词："不正确的"、"错误的"、"以下哪项除外"、"不属于"等
- 对于单选题，只给出一个选项字母（如 A）
- 对于多选题，给出所有正确选项字母（如 A,C,D）

### 填空题
- 给出简洁、准确的答案
- 如果有多个空，用 | 分隔每个空的答案
- **数值答案格式**（非常重要）：
  - 如果题目明确要求 "exact value"（精确值），使用分数或根号等精确形式，如 `sqrt(3)/2`、`1/3`
  - 如果题目要求 "round to the nearest hundredth"（四舍五入到百分位）或类似的近似要求，给出小数形式，如 `0.87`
  - 如果题目同时说 "Enter an exact value or round to the nearest hundredth"，优先使用小数形式（更不容易出现格式错误）
  - 如果题目没有明确说明格式，默认使用小数形式（保留两位小数）
  - 不要使用 LaTeX 语法（如 \frac{}{}、\sqrt{}）
  - 分数如果必须使用，写成 `1/2` 而非其他格式
- **注意题目中的格式提示**：仔细阅读题目对答案格式的要求（如 "as a fraction", "in simplest form", "to 2 decimal places" 等），严格按要求输出

### 判断题
- 回答"正确"或"错误"（或"对"/"错"、"True"/"False"，与题目格式匹配）

### 简答题 / 论述题
- 给出完整、有条理的答案
- 包含关键知识点，逻辑清晰

### 计算题
- 先展示完整的计算过程
- 最后明确给出最终答案

## 输出格式

**必须严格按以下格式输出，ANSWER 在前，REASONING 在后，不要添加额外说明：**

ANSWER:
（最终答案。选择题只写选项字母，填空题写填入的内容，判断题写对/错，简答题写完整答案）

REASONING:
（简洁的推理过程。选择题/判断题/填空题只需 2-3 句关键推理；简答题/论述题可以详细一些）
"""

# ============================================================
# Browser Agent 的追加系统提示（仅关注浏览器操作流程）
# ============================================================
BROWSER_AGENT_PROMPT = """
## 做题操作指令

### 你的角色
你是一个浏览器自动化操作员。你的任务是在网页上识别题目，调用 solve_question 工具获取答案，然后将答案填入页面。

### 核心工作流程（严格遵循）
对于页面上的每一道题目：
1. **提取题目**：仔细阅读题目的完整文本，包括题干、所有选项（如有）、以及题目类型提示
2. **调用 solve_question**：将题目完整内容传给 solve_question 工具，获取答案
3. **填入答案**：根据返回的答案，在页面上执行对应操作（点击选项 / 输入文字）
4. **继续下一题**：重复以上步骤

### 题目提取要求
调用 solve_question 时，question 参数必须包含：
- 完整的题干文字
- 题目类型（选择题/填空题/判断题/简答题）
- 如果是选择题，列出所有选项及其内容（如 "A. xxx  B. xxx  C. xxx  D. xxx"）
- 如果有图片或公式等上下文信息，用文字描述
- **重要：如果题目有格式要求**（如 "round to the nearest hundredth"、"enter an exact value"、"as a fraction" 等），必须在 question 中原样包含这些要求
- 如果输入框旁边有格式提示或示例（如 placeholder 文字），也要包含在 question 中

### 填入答案的格式注意事项
- **填入前必须先清空输入框**：先三击（triple-click）选中输入框全部内容，或使用 Ctrl+A 全选，然后再输入新内容。绝不能在旧内容后面追加。
- **修正错误格式时**：如果之前填入的格式不被接受，必须先完全清空输入框（三击选中 → 删除，或 Ctrl+A → Delete），确认输入框为空后再输入新格式的答案。
- 如果 solver 返回的答案格式不被接受（如页面报错或显示格式不正确），尝试将答案转换为小数形式后重新填入。
- 对于坐标类答案，注意页面可能有两个独立输入框（分别输入 x 和 y），不要把整个 "(x, y)" 粘贴到一个框里。
- 填入答案后，检查输入框中显示的内容是否与预期一致，如果不一致则清空重新输入。

### 翻页与提交逻辑
- 完成当前页面所有题目后，查找"下一页"/"下一题"/"Next"/"继续"等按钮并点击
- 如果找到"提交"/"Submit"/"交卷"按钮，先检查是否所有题目已作答完毕，然后点击提交
- 如果页面有进度条或题目编号，利用它们判断是否还有未完成的题目

### 重要注意事项
- **必须使用 solve_question 工具获取答案**，不要自己猜测答案
- 每次操作后等待页面加载完毕再进行下一步
- 如果遇到弹窗（如确认提交的对话框），根据情况点击确认或取消
- 如果遇到验证码或需要人工干预的情况，停下来等待
"""

# ============================================================
# 任务描述
# ============================================================
TASK_DESCRIPTION = """请完成当前页面上的所有题目。

操作步骤：
1. 仔细浏览页面，识别所有题目
2. 对每道题，提取完整题目内容（题干 + 选项），调用 solve_question 工具获取答案
3. 根据 solve_question 返回的答案，在页面上点击选项或输入文字来作答（如果在作答时格式错误，必须先用 Ctrl+A 全选清空输入框，再输入新格式的答案）
4. 完成当前页所有题目后，如果有"下一页"按钮则点击继续
5. 直到所有题目完成，最后点击"提交"按钮
"""


# ============================================================
# 自定义 Tool：solve_question（调用独立 Solver LLM）
# ============================================================
class SolveQuestionParams(BaseModel):
    """solve_question 工具的参数模型"""
    question: str = Field(
        description='完整的题目内容，包括题干、选项（如有）、题目类型。'
                    '示例："【单选题】以下哪个是中国的首都？A. 上海  B. 北京  C. 广州  D. 深圳"'
    )
    question_type: str = Field(
        default='auto',
        description='题目类型：choice（选择题）、fill（填空题）、judge（判断题）、essay（简答题）、auto（自动识别）'
    )
    answer_format_hint: str = Field(
        default='',
        description='答案格式提示，从题目中提取的格式要求。'
                    '例如："round to the nearest hundredth"、"enter an exact value"、"as a fraction"、"to 2 decimal places"。'
                    '如果没有特殊格式要求，留空即可。'
    )


def create_solver_tool(tools: Tools, solver_llm: BaseChatModel) -> None:
    """注册 solve_question 自定义工具，内部调用独立的 Solver LLM 进行解题。"""

    @tools.action(
        'Solve a question: send the complete question text to the solver AI and get the answer. '
        'You MUST use this tool for every question before filling in answers on the page. '
        'Include the full question text with all options.',
        param_model=SolveQuestionParams,
    )
    async def solve_question(params: SolveQuestionParams) -> ActionResult:
        """调用 Solver LLM 解答题目，返回推理过程和答案。"""
        logger.info(f'🧠 Solver 收到题目：{params.question[:80]}...')

        # 构建 Solver 的消息（纯文本推理，无浏览器上下文）
        type_hint = ''
        if params.question_type != 'auto':
            type_map = {
                'choice': '这是一道选择题',
                'fill': '这是一道填空题',
                'judge': '这是一道判断题',
                'essay': '这是一道简答题/论述题',
            }
            type_hint = f'\n\n提示：{type_map.get(params.question_type, "")}'

        # 附加格式要求
        format_hint = ''
        if params.answer_format_hint:
            format_hint = f'\n\n答案格式要求：{params.answer_format_hint}'
        elif params.question_type == 'fill':
            format_hint = '\n\n答案格式要求：请优先使用小数形式（保留两位小数），不要使用 LaTeX 或特殊符号。'

        user_content = f'请解答以下题目：\n\n{params.question}{type_hint}{format_hint}'

        messages = [
            SystemMessage(content=SOLVER_SYSTEM_PROMPT),
            UserMessage(content=user_content),
        ]

        # 调用独立的 Solver LLM（返回 ChatInvokeCompletion，答案在 .completion 中）
        response = await solver_llm.ainvoke(messages)
        answer_text = response.completion if isinstance(response.completion, str) else str(response.completion)

        logger.info(f'✅ Solver 返回答案 ({len(answer_text)} 字符)')

        # 解析答案（新格式：ANSWER 在前，REASONING 在后）
        answer_part = answer_text
        reasoning_part = ''
        if 'ANSWER:' in answer_text:
            after_answer = answer_text.split('ANSWER:', 1)[-1]
            if 'REASONING:' in after_answer:
                answer_part = after_answer.split('REASONING:', 1)[0].strip()
                reasoning_part = after_answer.split('REASONING:', 1)[1].strip()
            else:
                answer_part = after_answer.strip()

        logger.info(f'✅ 解析答案：{answer_part}')

        # 根据题目类型智能截断推理过程，保留完整答案
        reasoning_limits = {
            'choice': 200,
            'judge': 150,
            'fill': 300,
            'essay': 1500,
            'auto': 500,
        }
        max_reasoning = reasoning_limits.get(params.question_type, 500)
        truncated_reasoning = reasoning_part[:max_reasoning]
        if len(reasoning_part) > max_reasoning:
            truncated_reasoning += '...(推理已截断)'

        # 组装返回内容：答案始终完整，推理按题型截断
        result_content = f'ANSWER: {answer_part}'
        if truncated_reasoning:
            result_content += f'\n\nREASONING: {truncated_reasoning}'

        return ActionResult(
            extracted_content=f'题目答案：\n{result_content}',
            long_term_memory=f'题目：{params.question[:100]}... → 答案：{answer_part}',
        )


# ============================================================
# 环境验证与工厂函数
# ============================================================
def validate_environment() -> None:
    """检查必要的环境变量是否已配置。"""
    provider = os.getenv('MODEL_PROVIDER', 'openai').lower()

    if provider == 'openai':
        if not os.getenv('OPENAI_API_KEY'):
            print('❌ 错误：未设置 OPENAI_API_KEY 环境变量。')
            print('   请在 .env 文件中设置 OPENAI_API_KEY=your-api-key-here')
            sys.exit(1)
    elif provider == 'anthropic':
        if not os.getenv('ANTHROPIC_API_KEY'):
            print('❌ 错误：未设置 ANTHROPIC_API_KEY 环境变量。')
            print('   请在 .env 文件中设置 ANTHROPIC_API_KEY=your-api-key-here')
            sys.exit(1)
    else:
        print(f'❌ 错误：不支持的 MODEL_PROVIDER "{provider}"，请使用 "openai" 或 "anthropic"。')
        sys.exit(1)


def _create_openai_llm(
    model: str | None = None,
    base_url: str | None = None,
    max_completion_tokens: int | None = None,
) -> ChatOpenAI:
    """创建 OpenAI LLM 实例。"""
    model = model or os.getenv('OPENAI_MODEL', 'gpt-4o')
    base_url = base_url or os.getenv('OPENAI_BASE_URL', None)
    kwargs = {'model': model}
    if base_url:
        kwargs['base_url'] = base_url
    if max_completion_tokens is not None:
        kwargs['max_completion_tokens'] = max_completion_tokens
    return ChatOpenAI(**kwargs)


def _create_anthropic_llm(model: str | None = None) -> ChatAnthropic:
    """创建 Anthropic LLM 实例。"""
    model = model or os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')
    return ChatAnthropic(model=model)


def create_llms() -> tuple[BaseChatModel, BaseChatModel]:
    """创建 Browser Agent LLM 和 Solver LLM。

    支持通过环境变量为两个角色配置不同模型：
    - BROWSER_MODEL：浏览器操作模型（默认使用 OPENAI_MODEL）
    - SOLVER_MODEL：解题推理模型（默认使用 OPENAI_MODEL）
    """
    provider = os.getenv('MODEL_PROVIDER', 'openai').lower()

    browser_model = os.getenv('BROWSER_MODEL', None)
    solver_model = os.getenv('SOLVER_MODEL', None)

    if provider == 'openai':
        browser_llm = _create_openai_llm(model=browser_model)
        solver_llm = _create_openai_llm(model=solver_model, max_completion_tokens=16384)
        print(f'🤖 Browser Agent 模型：OpenAI {browser_llm.model}')
        print(f'🧠 Solver Agent 模型：OpenAI {solver_llm.model}')
        base_url = os.getenv('OPENAI_BASE_URL', None)
        if base_url:
            print(f'   API 地址：{base_url}')
    elif provider == 'anthropic':
        browser_llm = _create_anthropic_llm(model=browser_model)
        solver_llm = _create_anthropic_llm(model=solver_model)
        print(f'🤖 Browser Agent 模型：Anthropic {browser_llm.model}')
        print(f'🧠 Solver Agent 模型：Anthropic {solver_llm.model}')
    else:
        raise ValueError(f'不支持的 MODEL_PROVIDER: {provider}')

    return browser_llm, solver_llm


def create_browser_session() -> BrowserSession:
    """创建连接到本地 Chrome 的 BrowserSession。"""
    cdp_url = os.getenv('CDP_URL', 'http://localhost:9222')
    print(f'🌐 连接 Chrome CDP：{cdp_url}')

    return BrowserSession(
        browser_profile=BrowserProfile(
            cdp_url=cdp_url,
            is_local=True,
            # 适当增加等待时间，应对教育平台页面加载延迟
            minimum_wait_page_load_time=0.5,
            wait_for_network_idle_page_load_time=1.0,
            wait_between_actions=0.3,
        )
    )


# ============================================================
# 主函数
# ============================================================
async def main():
    """主函数：初始化双 Agent 架构并运行做题任务。"""
    print('=' * 60)
    print('  📚 StudyAgent — 自动做题 Agent（双 Agent 架构）')
    print('=' * 60)
    print()

    # 1. 验证环境变量
    validate_environment()

    # 2. 创建 LLM 实例（Browser Agent + Solver Agent 可使用不同模型）
    browser_llm, solver_llm = create_llms()

    # 3. 创建带 solve_question 工具的 Tools
    tools = Tools()
    create_solver_tool(tools, solver_llm)
    print('🔧 已注册自定义工具：solve_question')

    # 4. 创建浏览器会话
    browser_session = create_browser_session()

    try:
        # 5. 创建 Browser Agent
        agent = Agent(
            task=TASK_DESCRIPTION,
            llm=browser_llm,
            tools=tools,
            browser_session=browser_session,
            use_vision=True,            # 启用截图理解（用于识别题目）
            use_thinking=True,          # 启用思维链
            max_actions_per_step=3,     # 每步最多 3 个动作
            max_failures=5,             # 允许更多重试
            max_steps=200,              # 足够完成大量题目
            enable_planning=True,       # 启用计划功能
            use_judge=True,             # 任务完成判断
            extend_system_message=BROWSER_AGENT_PROMPT,
            demo_mode=True,             # 高亮操作元素，方便观察
        )

        print()
        print('🚀 Agent 开始做题...')
        print('   架构：Browser Agent（操作页面）→ Solver Agent（解题推理）')
        print('   （按 Ctrl+C 可随时中止）')
        print()

        # 6. 运行 Agent
        result = await agent.run()

        # 7. 输出结果摘要
        print()
        print('=' * 60)
        print('  ✅ 做题完成！')
        print('=' * 60)
        if result:
            final = result.final_result()
            if final:
                print(f'📋 结果摘要：{final}')
            print(f'📊 总步骤数：{len(result.history)}')
            errors = result.errors()
            if errors:
                print(f'⚠️  遇到 {len(errors)} 个错误')

    except KeyboardInterrupt:
        print('\n\n⏹️  用户中止，正在清理...')
    except Exception as e:
        error_msg = str(e)
        if 'connect' in error_msg.lower() or 'cdp' in error_msg.lower():
            print(f'\n❌ 无法连接到 Chrome，请检查：')
            print(f'   1. Chrome 是否已以 debug 模式启动？')
            print(f'   2. 启动命令：chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\chrome-debug-profile"')
            print(f'   3. 验证方式：浏览器访问 http://localhost:9222/json/version')
        else:
            print(f'\n❌ 运行出错：{e}')
        raise
    finally:
        # 8. 清理：断开 CDP 连接（不会关闭用户的 Chrome）
        print('🔌 断开浏览器连接...')
        await browser_session.kill()
        print('👋 已退出。')


if __name__ == '__main__':
    asyncio.run(main())

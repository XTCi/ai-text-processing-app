from typing import AsyncIterator

from models.events import TaskEvent
from models.task import FunctionType, ModelMode
from services.llm_client import stream_completion

_DIRECTION_LABEL = {
    FunctionType.TRANSLATE_EN2ZH: "英译中",
    FunctionType.TRANSLATE_ZH2EN: "中译英",
}


def _draft_messages(text: str, function_type: FunctionType) -> list[dict]:
    label = _DIRECTION_LABEL[function_type]
    return [
        {"role": "system", "content": f"你是专业翻译，请将用户输入做{label}翻译，只输出译文。"},
        {"role": "user", "content": text},
    ]


def _review_messages(original: str, draft: str, function_type: FunctionType) -> list[dict]:
    label = _DIRECTION_LABEL[function_type]
    return [
        {
            "role": "system",
            "content": (
                f"你是专业译审，请检查以下{label}翻译是否准确、完整、通顺。"
                "如需修改，只输出修正后的完整译文；如果不需要修改，原样输出初稿译文。不要输出解释。"
            ),
        },
        {"role": "user", "content": f"原文：{original}\n初稿译文：{draft}"},
    ]


async def run_translate(text: str, function_type: FunctionType, mode: ModelMode) -> AsyncIterator[TaskEvent]:
    draft_text = ""
    async for delta in stream_completion(_draft_messages(text, function_type), ModelMode.FAST):
        draft_text += delta
        yield TaskEvent(type="token", stage="draft", delta=delta)

    if mode != ModelMode.THINK:
        yield TaskEvent(type="done", result=draft_text)
        return

    yield TaskEvent(type="progress", stage="review", message="精修中...")
    review_text = ""
    async for delta in stream_completion(_review_messages(text, draft_text, function_type), ModelMode.THINK):
        review_text += delta
        yield TaskEvent(type="token", stage="review", delta=delta)

    yield TaskEvent(type="done", result=review_text or draft_text)

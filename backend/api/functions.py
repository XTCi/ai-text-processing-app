from fastapi import APIRouter

router = APIRouter()

_FUNCTIONS = [
    {"id": "translate_en2zh", "name": "英译中", "description": "将英文文本翻译为中文"},
    {"id": "translate_zh2en", "name": "中译英", "description": "将中文文本翻译为英文"},
    {"id": "summarize", "name": "文本总结", "description": "对长文本生成要点总结"},
]


@router.get("/api/functions")
async def list_functions() -> dict:
    return {"functions": _FUNCTIONS}

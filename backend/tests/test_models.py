# backend/tests/test_models.py
import pytest
from pydantic import ValidationError as PydanticValidationError

from models.task import FunctionType, ModelMode, TaskSubmitRequest, resolve_mode
from models.events import TaskEvent


@pytest.mark.parametrize(
    "function_type,mode,expected",
    [
        (FunctionType.TRANSLATE_EN2ZH, "auto", ModelMode.FAST),
        (FunctionType.TRANSLATE_ZH2EN, "auto", ModelMode.FAST),
        (FunctionType.SUMMARIZE, "auto", ModelMode.THINK),
        (FunctionType.TRANSLATE_EN2ZH, "think", ModelMode.THINK),
        (FunctionType.SUMMARIZE, "fast", ModelMode.FAST),
    ],
)
def test_resolve_mode(function_type, mode, expected):
    assert resolve_mode(function_type, mode) == expected


def test_task_submit_request_rejects_empty_text():
    with pytest.raises(PydanticValidationError):
        TaskSubmitRequest(function_type=FunctionType.SUMMARIZE, text="")


def test_task_event_defaults():
    event = TaskEvent(type="token", stage="draft", delta="他")
    assert event.result is None
    assert event.chunk_index is None

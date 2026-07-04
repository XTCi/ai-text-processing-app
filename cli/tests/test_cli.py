# cli/tests/test_cli.py
from unittest.mock import patch

from click.testing import CliRunner

from ai_app.main import cli


def test_translate_command_streams_output():
    with patch("ai_app.main.submit_task", return_value="task-1") as mock_submit, patch(
        "ai_app.main.stream_task",
        return_value=iter(
            [
                {"type": "token", "stage": "draft", "delta": "你"},
                {"type": "token", "stage": "draft", "delta": "好"},
                {"type": "done", "result": "你好"},
            ]
        ),
    ) as mock_stream:
        runner = CliRunner()
        result = runner.invoke(cli, ["translate", "--text", "Hello", "--from", "en", "--to", "zh"])

    assert result.exit_code == 0
    assert "你好" in result.output
    mock_submit.assert_called_once()
    assert mock_submit.call_args.kwargs["function_type"] == "translate_en2zh"
    mock_stream.assert_called_once_with("http://localhost:8000", "task-1", transport=None)


def test_summarize_command_passes_max_points():
    with patch("ai_app.main.submit_task", return_value="task-2") as mock_submit, patch(
        "ai_app.main.stream_task",
        return_value=iter([{"type": "done", "result": "要点1；要点2"}]),
    ):
        runner = CliRunner()
        result = runner.invoke(cli, ["summarize", "--text", "长文本", "--max-points", "2"])

    assert result.exit_code == 0
    assert "要点1；要点2" in result.output
    assert mock_submit.call_args.kwargs["max_points"] == 2


def test_translate_rejects_unknown_direction():
    runner = CliRunner()
    result = runner.invoke(cli, ["translate", "--text", "Hello", "--from", "fr", "--to", "zh"])
    assert result.exit_code != 0

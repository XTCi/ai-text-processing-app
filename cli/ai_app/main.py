# cli/ai_app/main.py
import sys

import click

from ai_app.client import cancel_task, stream_task, submit_task

_DIRECTION_MAP = {
    ("en", "zh"): "translate_en2zh",
    ("zh", "en"): "translate_zh2en",
}


@click.group()
def cli() -> None:
    """AI text processing CLI — translate/summarize via the backend API."""


def _run_and_stream(base_url: str, function_type: str, text: str, max_points: int | None) -> None:
    task_id = submit_task(base_url, function_type=function_type, text=text, max_points=max_points)
    streamed_any_token = False
    try:
        for event in stream_task(base_url, task_id, transport=None):
            if event["type"] == "token":
                streamed_any_token = True
                click.echo(event["delta"], nl=False)
            elif event["type"] == "progress" and event.get("message"):
                click.echo(f"\n[{event['message']}]", nl=False)
            elif event["type"] == "done":
                if not streamed_any_token and event.get("result") is not None:
                    click.echo(event["result"], nl=False)
                click.echo()
            elif event["type"] == "error":
                click.echo(f"\n[error] {event.get('message')}", err=True)
                sys.exit(1)
            elif event["type"] == "cancelled":
                click.echo("\n[cancelled]")
                sys.exit(1)
    except KeyboardInterrupt:
        cancel_task(base_url, task_id)
        click.echo("\n[cancelled]")
        sys.exit(1)


def _resolve_text(text: str | None, text_file: str | None) -> str:
    if text is not None and text_file is not None:
        raise click.UsageError("pass either --text or --text-file, not both")
    if text is None and text_file is None:
        raise click.UsageError("one of --text or --text-file is required")
    if text_file is not None:
        with open(text_file, encoding="utf-8") as f:
            return f.read().rstrip("\n")
    return text


@cli.command()
@click.option("--text", default=None)
@click.option("--text-file", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--from", "from_lang", required=True, type=click.Choice(["en", "zh"]))
@click.option("--to", "to_lang", required=True, type=click.Choice(["en", "zh"]))
@click.option("--host", default="http://localhost:8000")
def translate(text: str | None, text_file: str | None, from_lang: str, to_lang: str, host: str) -> None:
    resolved_text = _resolve_text(text, text_file)
    function_type = _DIRECTION_MAP.get((from_lang, to_lang))
    if function_type is None:
        raise click.BadParameter(f"unsupported direction {from_lang}->{to_lang}")
    _run_and_stream(host, function_type, resolved_text, None)


@cli.command()
@click.option("--text", default=None)
@click.option("--text-file", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--max-points", default=3, type=int)
@click.option("--host", default="http://localhost:8000")
def summarize(text: str | None, text_file: str | None, max_points: int, host: str) -> None:
    resolved_text = _resolve_text(text, text_file)
    _run_and_stream(host, "summarize", resolved_text, max_points)

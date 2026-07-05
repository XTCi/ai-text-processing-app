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


@cli.command()
@click.option("--text", required=True)
@click.option("--from", "from_lang", required=True, type=click.Choice(["en", "zh"]))
@click.option("--to", "to_lang", required=True, type=click.Choice(["en", "zh"]))
@click.option("--host", default="http://localhost:8000")
def translate(text: str, from_lang: str, to_lang: str, host: str) -> None:
    function_type = _DIRECTION_MAP.get((from_lang, to_lang))
    if function_type is None:
        raise click.BadParameter(f"unsupported direction {from_lang}->{to_lang}")
    _run_and_stream(host, function_type, text, None)


@cli.command()
@click.option("--text", required=True)
@click.option("--max-points", default=3, type=int)
@click.option("--host", default="http://localhost:8000")
def summarize(text: str, max_points: int, host: str) -> None:
    _run_and_stream(host, "summarize", text, max_points)

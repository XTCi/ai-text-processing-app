# cli/ai_app/client.py
import json
from typing import Iterator

import httpx


def submit_task(
    base_url: str,
    function_type: str,
    text: str,
    max_points: int | None,
    mode: str = "auto",
    transport: httpx.BaseTransport | None = None,
) -> str:
    with httpx.Client(base_url=base_url, transport=transport) as client:
        resp = client.post(
            "/api/task",
            json={"function_type": function_type, "text": text, "max_points": max_points, "mode": mode},
        )
        resp.raise_for_status()
        return resp.json()["task_id"]


def stream_task(base_url: str, task_id: str, transport: httpx.BaseTransport | None = None) -> Iterator[dict]:
    with httpx.Client(base_url=base_url, transport=transport) as client:
        with client.stream("GET", f"/api/task/{task_id}/stream") as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                yield json.loads(line[len("data: "):])


def cancel_task(base_url: str, task_id: str, transport: httpx.BaseTransport | None = None) -> None:
    with httpx.Client(base_url=base_url, transport=transport) as client:
        resp = client.delete(f"/api/task/{task_id}")
        resp.raise_for_status()

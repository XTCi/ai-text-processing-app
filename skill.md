# ai-app CLI skill

## What this does
Calls a running AI text-processing backend to translate text between English
and Chinese, or to summarize long text into a bounded number of points.
Streams output token-by-token to stdout as the model generates it.

## When to use this
- User asks to translate text between English and Chinese.
- User asks to summarize or condense a long piece of text.

## Prerequisites
The backend (`backend/main.py`) and worker (`backend/worker/settings.py`) must
be running, e.g. via `docker compose up` from the repo root, or with
`--host` pointed at wherever they're running (default `http://localhost:8000`).

## Commands

Translate English to Chinese:
```bash
ai-app translate --text "Hello, world" --from en --to zh
```

Translate Chinese to English:
```bash
ai-app translate --text "你好，世界" --from zh --to en
```

Summarize long text into at most N points:
```bash
ai-app summarize --text "<long text>" --max-points 3
```

Point at a non-default backend:
```bash
ai-app translate --text "Hello" --from en --to zh --host http://localhost:8000
```

## Output
Streams the result to stdout as plain text; the command exits 0 on success.
Press Ctrl+C to cancel an in-flight request — the CLI notifies the backend
so the task queue stops processing it.

## Installation
```bash
cd cli && pip install -e .
```

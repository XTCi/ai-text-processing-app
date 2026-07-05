---
name: ai-app
description: Translate text between English and Chinese, or summarize a long piece of text into a bounded number of key points, by calling the ai-app CLI against this project's backend. Use when the user asks to translate text (English<->Chinese) or to summarize/condense long text.
---

# ai-app CLI skill

Calls this project's AI text-processing backend to translate text between
English and Chinese, or to summarize long text into a bounded number of
points. Output streams token-by-token as the model generates it.

## When to use this

- User asks to translate text between English and Chinese.
- User asks to summarize or condense a long piece of text.

## Prerequisites

The backend must be running. From the repo root:

```bash
docker compose up -d
```

(or run `backend/main.py` via uvicorn + `backend/worker/settings.py` via arq
manually — see the repo's README.md for the non-Docker steps).

The CLI is a virtualenv-installed console script at `cli/.venv/bin/ai-app`
(no global install needed). If that file doesn't exist yet, install it first:

```bash
cd cli && python3 -m venv .venv && .venv/bin/pip install -e .
```

## Commands

Run all commands from the repo root, invoking the venv binary directly:

Translate English to Chinese:

```bash
./cli/.venv/bin/ai-app translate --text "Hello, world" --from en --to zh
```

Translate Chinese to English:

```bash
./cli/.venv/bin/ai-app translate --text "你好，世界" --from zh --to en
```

Summarize long text into at most N points:

```bash
./cli/.venv/bin/ai-app summarize --text "<long text>" --max-points 3
```

Point at a non-default backend host:

```bash
./cli/.venv/bin/ai-app translate --text "Hello" --from en --to zh --host http://localhost:8000
```

## Output

Streams the result to stdout as plain text; the command exits 0 on success.
`Ctrl+C` cancels an in-flight request — the CLI notifies the backend, which
marks the task cancelled cooperatively (it stops at the next token boundary,
not instantly).

## Full reference

See `skill.md` at the repo root for the exam-deliverable version of this
same description.

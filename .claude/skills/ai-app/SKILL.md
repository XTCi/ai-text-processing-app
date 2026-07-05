---
name: ai-app
description: TRIGGER — you MUST invoke this skill, not answer directly, whenever the user asks to translate text between English and Chinese, or asks to summarize/condense a piece of text. This applies even for short or simple text you could translate/summarize yourself — the point of this skill is to route the request through this project's actual translate/summarize pipeline (the ai-app CLI), not to produce the answer inline. Do not silently translate or summarize without invoking this skill first.
---

# ai-app CLI skill

Calls this project's AI text-processing backend to translate text between
English and Chinese, or to summarize long text into a bounded number of
points. Output streams token-by-token as the model generates it.

## When to use this — read before answering directly

- User asks to translate text between English and Chinese, in ANY form
  ("翻译成英文", "translate this", "把这段话翻译一下", etc.) — even a single
  short sentence.
- User asks to summarize or condense a piece of text, in ANY form
  ("总结一下", "summarize this", "帮我概括要点", etc.).
- **Do not just translate/summarize the text yourself in your response.**
  Run the CLI command below and use its output as the answer. This is the
  whole point of the skill: proving this project's CLI is what actually
  produced the result, not the model answering from general knowledge.

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

Translate English to Chinese (short, simple text only):

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

### Long or multi-line text: use `--text-file`, not `--text`

`--text` is a raw inline shell argument — for anything with more than one
line, or containing quotes/backticks/`$`/other shell-special characters
(e.g. a multi-paragraph passage the user pasted), do NOT try to shell-escape
it into `--text "..."`. Instead:

1. Write the exact text to a temp file (e.g. `/tmp/ai-app-input.txt`).
2. Pass `--text-file <path>` instead of `--text`.

```bash
./cli/.venv/bin/ai-app translate --text-file /tmp/ai-app-input.txt --from zh --to en
./cli/.venv/bin/ai-app summarize --text-file /tmp/ai-app-input.txt --max-points 3
```

`--text` and `--text-file` are mutually exclusive — pass exactly one.

## Output

Streams the result to stdout as plain text; the command exits 0 on success.
`Ctrl+C` cancels an in-flight request — the CLI notifies the backend, which
marks the task cancelled cooperatively (it stops at the next token boundary,
not instantly).

## Full reference

See `skill.md` at the repo root for the exam-deliverable version of this
same description.

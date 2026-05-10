# Technical Context

## Runtime

- Python 3.11+
- Textual `0.79.1`
- SQLModel + SQLite via `aiosqlite`
- Rich rendering through Textual widgets
- `uv` for local development and editable tool install

## CLI Entrypoints

`pyproject.toml` exposes:

```toml
[project.scripts]
cafedelia = "elia_chat.__main__:cli"
cafidelia = "elia_chat.__main__:cli"
```

Installed editable with:

```bash
uv tool install --force --editable /home/alex/code/cafedelia
```

## Agent Commands

Claude Code:

```bash
cnd -p --verbose --output-format stream-json
cnd -p --verbose --output-format stream-json --resume <session_id>
```

Codex:

```bash
codex exec --json --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox
codex exec resume --json --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox <thread_id>
```

`cnd` is expected to be a user shell alias/function that runs Claude Code with permission prompts bypassed. The adapter invokes it through `bash -ic` so the shell setup is available.

## Key Files

- `elia_chat/__main__.py`: CLI commands and launch modes.
- `elia_chat/app.py`: Textual app screen routing.
- `elia_chat/database/models.py`: legacy chat tables plus room tables.
- `elia_chat/rooms/manager.py`: async room persistence API.
- `elia_chat/rooms/routing.py`: recipient parsing.
- `elia_chat/agents/claude_code.py`: Claude subprocess adapter.
- `elia_chat/agents/codex_cli.py`: Codex subprocess adapter.
- `elia_chat/agents/parsers.py`: JSONL normalization.
- `elia_chat/widgets/room_chat.py`: group room widget.
- `elia_chat/widgets/room_message.py`: message panel rendering.
- `elia_chat/widgets/chat_list.py`: merged room/chat history list.
- `elia_chat/widgets/app_header.py`: group identity label.

## Validation Commands

```bash
python3 -m compileall elia_chat
uv run --frozen black --check elia_chat
cafedelia --help
cafidelia room --help
```

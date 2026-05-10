# Active Context

## Current State

- **Date**: May 10, 2026
- **Focus**: Old-Elia UX with Claude Code × Codex as the primary chat backend
- **Status**: Proof of concept implemented, validated, and ready for iterative hardening

## What Changed

Cafedelia now keeps the familiar Elia shell while adding a persisted group-room subsystem:

- Home/header/history remain the entry point for normal `cafedelia` launches.
- The header model label now reads `Group · Claude Code × Codex`.
- Home prompt submission opens/sends to the group room.
- Room history is shown in the existing chat history list as first-class entries.
- `Esc` from the room returns to the home/history UI instead of feeling like a separate app.

## Agent Runtime Model

- Claude Code is invoked through the user's `cnd` shell alias with `-p`.
- The Claude adapter runs through `bash -ic` so aliases/functions from interactive shell setup resolve correctly.
- Codex is invoked through `codex exec --json`.
- Both streams are parsed as JSONL and normalized into room messages.
- Agent metadata is persisted in room messages and reused for session resume:
  - Claude: `session_id` from stream-json system/result events.
  - Codex: `thread_id` from `thread.started` events.

## Current Implementation Areas

- `elia_chat/rooms/`: room persistence manager and routing helpers.
- `elia_chat/agents/`: subprocess adapters and stream parsers.
- `elia_chat/widgets/room_chat.py`: Textual group chat widget.
- `elia_chat/widgets/chat_list.py`: merged history list containing rooms and legacy chats.
- `elia_chat/widgets/app_header.py`: group identity label.
- `elia_chat/__main__.py`: `cafedelia`, `cafidelia`, `room`, `send`, and `post` command paths.

## Known Risks / Next Hardening

- Textual alternate-screen crashes can hide tracebacks; use logs or non-alt-screen debugging when reproducing exits.
- Legacy API chat support remains in the codebase but is no longer the primary path.
- Codex/Claude JSONL event shapes can change; parsers should stay defensive and small.
- Room history currently loads recent messages per room; optimize if room count grows.

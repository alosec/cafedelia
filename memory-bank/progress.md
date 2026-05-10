# Progress

## Current Status: Group Chat Primary UX Implemented

**Date**: May 10, 2026
**Phase**: Claude Code × Codex group-room proof of concept
**Next Phase**: Runtime hardening and polish

## Completed

- [x] Added room persistence tables: `room`, `actor`, `room_message`, `agent_run`.
- [x] Added `RoomManager` for room creation, history, message persistence, run tracking, archive, and metadata lookup.
- [x] Added Claude Code adapter using `cnd -p --verbose --output-format stream-json`.
- [x] Added Codex adapter using `codex exec --json --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox`.
- [x] Added JSONL parsers for Claude and Codex output.
- [x] Added Textual room UI rendering human, Claude, Codex, status, result, tool, and error messages.
- [x] Added routing syntax: default sends to both, `@claude` / `claude:` sends to Claude, `@codex` / `codex:` sends to Codex.
- [x] Added `cafedelia room`, `cafedelia send`, and `cafedelia post`.
- [x] Added `cafidelia` CLI alias.
- [x] Made the old Elia home prompt route to the group room.
- [x] Added room entries into the existing history list.
- [x] Updated header identity to `Group · Claude Code × Codex`.
- [x] Persisted Claude `session_id` and resumed future turns with `--resume`.
- [x] Persisted Codex `thread_id` and resumed future turns with `codex exec resume`.

## Validation Completed

- [x] `python3 -m compileall elia_chat`
- [x] `uv run --frozen black --check elia_chat`
- [x] CLI help smoke for `cafedelia` and `cafidelia room`.
- [x] Headless old-home launch test.
- [x] Headless home prompt → group room test.
- [x] Fake two-turn resume E2E proving Claude and Codex resume command construction.
- [x] Live Claude smoke response.
- [x] Live Codex smoke response.

## Open Follow-Ups

- [ ] Capture and surface hidden Textual crash traces.
- [ ] Add lightweight tests around room list rendering and route parsing.
- [ ] Add UI affordance for room title/rename.
- [ ] Consider pruning or hiding legacy API model settings now that group chat is primary.

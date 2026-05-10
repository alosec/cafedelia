# Cafedelia Project Brief

## Vision

Cafedelia is an Elia-based Textual app whose primary experience is a terminal-native group chat between the human user, Claude Code, and Codex. It preserves Elia's polished home/history/chat flow, but replaces the default single-model chat path with a persisted multi-agent room.

## Current Product Direction

- Keep the old Elia UX shape: home prompt, history list, selectable conversations, keyboard navigation, and beautiful Textual rendering.
- Make `Group · Claude Code × Codex` the primary "model" identity instead of showing a legacy API model such as `4o`.
- Treat Claude Code and Codex as subprocess-backed room participants, not hidden ETL imports.
- Preserve room state in Cafedelia SQLite and resume each underlying agent session when possible.

## Core Use Case

The user opens `cafedelia`, types a message in the familiar Elia home prompt, and lands in a group room where Claude Code and Codex both respond. Existing rooms appear in the history list alongside legacy chats, and reopening a room resumes the underlying Claude/Codex sessions using persisted IDs.

## Key Requirements

- `cafedelia` opens the old-style home UI.
- `cafedelia <prompt>` opens the group room and sends the prompt immediately.
- `cafedelia room` remains available as an explicit direct room command.
- `cafidelia` is supported as a CLI spelling alias.
- Claude launches through `cnd -p --verbose --output-format stream-json`.
- Claude resumes with `--resume <session_id>` after a session ID is observed.
- Codex launches through `codex exec --json --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox`.
- Codex resumes with `codex exec resume <thread_id> ...` after a thread ID is observed.

## Non-Goals

- Do not revive the stale `~/.claude/__store.db` sync path as the primary experience.
- Do not make this a separate minimal room app that bypasses the old Elia home/history UX.
- Do not depend on the old chokidar ETL for live chat.

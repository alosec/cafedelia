# Product Context

## Why Cafedelia Exists

Claude Code and Codex are powerful coding agents, but using them side-by-side normally means juggling separate terminals and mental context. Cafedelia turns Elia's polished Textual chat interface into a shared room where the user can ask both agents, compare answers, and keep a persistent record.

## Desired Experience

The app should feel like the original Elia:

- Launch into a clean home screen.
- Type into the top prompt.
- See prior conversations in a history list.
- Select an entry to continue it.
- Press `Esc` from a conversation to return home.

The difference is the primary model identity and behavior:

- The visible model is `Group · Claude Code × Codex`.
- Sending a message routes to Claude Code and Codex by default.
- The transcript stores both agents' outputs in one room.
- Reopening the room resumes underlying agent sessions where possible.

## User Controls

- Default route: send to Claude and Codex.
- `@claude` or `claude:`: send only to Claude.
- `@codex` or `codex:`: send only to Codex.
- `cafedelia send`: append a user message to the room from the shell.
- `cafedelia post --actor`: append a message as a specific actor.

## Product Boundaries

This is currently a proof of concept that prioritizes live group chat over historical ETL:

- The old Claude JSONL/chokidar ETL work is useful context but not the active path.
- The old API-model single-chat path remains in code but is not the product center.
- The core product is the room/event-bus experience around live subprocess agents.

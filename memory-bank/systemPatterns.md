# System Patterns

## Primary Pattern: Elia Shell + Room Backend

Cafedelia should preserve Elia's UX shell and replace the default chat backend with a group room:

```text
Home prompt / history list
        │
        ▼
RoomScreen
        │
        ▼
RoomChat widget
        │
        ├── ClaudeCodeAgent subprocess
        └── CodexCliAgent subprocess
```

## Persistence Pattern

Room state is stored separately from legacy Elia chats:

- `room`: room title, archive state, timestamps.
- `actor`: human, Claude, Codex, system metadata.
- `room_message`: normalized events from user/agents.
- `agent_run`: command/run status for each subprocess invocation.

The room transcript is built from recent `room_message` rows. Agent resume IDs are stored in message `meta` and found with `RoomManager.latest_actor_meta_value`.

## Agent Adapter Pattern

Adapters expose a shared async generator shape:

```python
async for event in adapter.run(prompt, transcript=transcript):
    await RoomManager.add_message(...)
```

Each adapter owns command construction and stream parsing details:

- Claude adapter builds `cnd -p --verbose --output-format stream-json [--resume id] <prompt>`.
- Codex adapter builds `codex exec ... <prompt>` or `codex exec resume ... <thread_id> <prompt>`.
- Parsers convert provider-specific JSONL events into `AgentEvent`.

## Resume Pattern

Resume is room-scoped:

1. First turn launches a fresh subprocess session.
2. Stream parser captures provider session identity:
   - Claude: `session_id`
   - Codex: `thread_id`
3. Identity is persisted in room message metadata.
4. Next turn in the same room reads latest identity and constructs resume command.

## UX Pattern

- `cafedelia` with no prompt opens the old home/history UI.
- `cafedelia <prompt>` opens the group room and submits immediately.
- The home prompt creates/opens a group room.
- The history list includes room entries and legacy chat entries.
- `Esc` in the room returns to home/history.
- The header model label is fixed to `Group · Claude Code × Codex`.

from __future__ import annotations

import json
from typing import Any

from elia_chat.agents.base import AgentEvent


def parse_json_line(line: bytes | str) -> dict[str, Any] | None:
    text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"type": "text", "content": text}


def content_blocks_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content) if content else ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"text", "output_text", "input_text"}:
            text = item.get("text", "")
            if text:
                parts.append(text)
        elif item_type == "tool_use":
            tool_name = item.get("name", "tool")
            tool_input = item.get("input") or {}
            params = summarize_mapping(tool_input)
            if params:
                parts.append(f"🛠️ Used `{tool_name}`\n{params}")
            else:
                parts.append(f"🛠️ Used `{tool_name}`")
        elif item_type == "tool_result":
            result = item.get("content", "")
            if result:
                parts.append(
                    f"📋 Tool result\n```text\n{truncate_text(str(result), 1200)}\n```"
                )
    return "\n\n".join(parts)


def summarize_mapping(value: dict[str, Any], max_items: int = 4) -> str:
    if not value:
        return ""
    lines = []
    for key, item in list(value.items())[:max_items]:
        if isinstance(item, (dict, list)):
            rendered = json.dumps(item, ensure_ascii=False)[:240]
        else:
            rendered = str(item)[:240]
        lines.append(f"- `{key}`: {rendered}")
    return "\n".join(lines)


def truncate_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n… truncated …"


def claude_event(actor_key: str, event: dict[str, Any]) -> AgentEvent | None:
    event_type = event.get("type")
    if event_type == "system":
        subtype = event.get("subtype")
        if subtype == "init":
            return AgentEvent(
                actor_key=actor_key,
                role="system",
                event_type="status",
                content=(
                    f"Initialized Claude session `{event.get('session_id', 'unknown')}` "
                    f"using `{event.get('model', 'unknown')}`."
                ),
                raw_json=event,
                meta={
                    "session_id": event.get("session_id"),
                    "model": event.get("model"),
                },
            )
        return None
    if event_type == "assistant":
        message = event.get("message") or {}
        content = content_blocks_to_text(message.get("content", ""))
        if not content:
            return None
        return AgentEvent(
            actor_key=actor_key,
            role="assistant",
            event_type="message",
            content=content,
            raw_json=event,
            meta={"model": message.get("model"), "usage": message.get("usage", {})},
        )
    if event_type == "result":
        content = event.get("result", "")
        if not content:
            content = (
                f"Completed in {event.get('duration_ms', 0)}ms; "
                f"turns={event.get('num_turns', 0)}."
            )
        return AgentEvent(
            actor_key=actor_key,
            role="assistant",
            event_type="result",
            content=content,
            raw_json=event,
            meta={
                "session_id": event.get("session_id"),
                "cost": event.get("total_cost_usd"),
                "duration_ms": event.get("duration_ms"),
                "turns": event.get("num_turns"),
            },
            is_final=True,
        )
    if event_type == "text":
        return AgentEvent(
            actor_key=actor_key,
            role="assistant",
            event_type="message",
            content=str(event.get("content", "")),
            raw_json=event,
        )
    return None


def codex_event(actor_key: str, event: dict[str, Any]) -> AgentEvent | None:
    if event.get("type") == "thread.started":
        thread_id = event.get("thread_id", "unknown")
        return AgentEvent(
            actor_key=actor_key,
            role="system",
            event_type="status",
            content=f"Started Codex thread `{thread_id}`.",
            raw_json=event,
            meta={"thread_id": thread_id},
        )

    if event.get("type") == "item.completed" and isinstance(event.get("item"), dict):
        payload = event["item"]
    else:
        payload = event.get("payload") or event
    payload_type = payload.get("type") or event.get("type")

    if payload_type in {
        "turn.started",
        "user_message",
        "token_count",
        "task_started",
        "reasoning",
    }:
        return None

    if payload_type in {"agent_message", "assistant_message", "message"}:
        content = (
            payload.get("message")
            or payload.get("text")
            or content_blocks_to_text(payload.get("content", ""))
        )
        role = payload.get("role") or "assistant"
        if content and role != "user":
            return AgentEvent(
                actor_key=actor_key,
                role="assistant",
                event_type="message",
                content=str(content),
                raw_json=event,
                meta={"codex_payload_type": payload_type},
            )

    if payload_type in {"function_call", "tool_call"}:
        name = payload.get("name") or payload.get("function", {}).get("name") or "tool"
        arguments = payload.get("arguments") or payload.get("input") or {}
        content = f"🛠️ Used `{name}`"
        params = (
            summarize_mapping(arguments)
            if isinstance(arguments, dict)
            else str(arguments)
        )
        if params:
            content += f"\n{params}"
        return AgentEvent(
            actor_key=actor_key,
            role="assistant",
            event_type="tool_call",
            content=content,
            raw_json=event,
        )

    if payload_type in {"function_call_output", "tool_result"}:
        output = payload.get("output") or payload.get("content") or ""
        return AgentEvent(
            actor_key=actor_key,
            role="tool",
            event_type="tool_result",
            content=f"📋 Tool result\n```text\n{truncate_text(str(output), 1200)}\n```",
            raw_json=event,
        )

    if payload_type in {
        "task_complete",
        "turn_complete",
        "turn.completed",
        "completed",
        "response.completed",
        "run_completed",
    }:
        content = (
            payload.get("message") or payload.get("text") or "Codex turn complete."
        )
        return AgentEvent(
            actor_key=actor_key,
            role="assistant",
            event_type="result",
            content=str(content),
            raw_json=event,
            is_final=True,
        )

    if event.get("type") == "text":
        return AgentEvent(
            actor_key=actor_key,
            role="assistant",
            event_type="message",
            content=str(event.get("content", "")),
            raw_json=event,
        )
    return None

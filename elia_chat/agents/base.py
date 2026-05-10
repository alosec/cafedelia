from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Protocol


@dataclass(frozen=True)
class AgentTarget:
    key: str
    name: str
    command: list[str]


@dataclass(frozen=True)
class AgentEvent:
    actor_key: str
    role: str
    event_type: str
    content: str
    raw_json: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    is_final: bool = False


class AgentAdapter(Protocol):
    target: AgentTarget

    async def run(
        self,
        prompt: str,
        *,
        transcript: str,
    ) -> AsyncGenerator[AgentEvent, None]: ...

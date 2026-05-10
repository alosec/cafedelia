from __future__ import annotations

import asyncio
import os
import shlex
from pathlib import Path
from typing import AsyncGenerator

from elia_chat.agents.base import AgentEvent, AgentTarget
from elia_chat.agents.parsers import claude_event, parse_json_line
from elia_chat.agents.prompts import build_group_prompt


class ClaudeCodeAgent:
    def __init__(
        self, cwd: Path | None = None, resume_session_id: str | None = None
    ) -> None:
        command = os.getenv("CAFEDELIA_CLAUDE_COMMAND", "cnd")
        self.cwd = cwd or Path.cwd()
        command_parts = [
            command,
            "-p",
            "--verbose",
            "--output-format",
            "stream-json",
        ]
        if resume_session_id:
            command_parts.extend(["--resume", resume_session_id])
        self.target = AgentTarget(
            key="claude",
            name="Claude Code",
            command=command_parts,
        )

    async def run(
        self,
        prompt: str,
        *,
        transcript: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        grouped_prompt = build_group_prompt(
            agent_name="Claude Code",
            peer_name="Codex",
            user_prompt=prompt,
            transcript=transcript,
        )
        command = [*self.target.command, grouped_prompt]
        process = await asyncio.create_subprocess_exec(
            "bash",
            "-ic",
            shlex.join(command),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
        )

        emitted_content: set[str] = set()
        assert process.stdout is not None
        async for line in process.stdout:
            parsed = parse_json_line(line)
            if parsed is None:
                continue
            event = claude_event(self.target.key, parsed)
            if event is None:
                continue
            if event.content in emitted_content and event.event_type == "result":
                event = AgentEvent(
                    actor_key=event.actor_key,
                    role=event.role,
                    event_type=event.event_type,
                    content="Claude Code turn complete.",
                    raw_json=event.raw_json,
                    meta=event.meta,
                    is_final=True,
                )
            emitted_content.add(event.content)
            yield event

        exit_code = await process.wait()
        if exit_code != 0:
            stderr = ""
            if process.stderr is not None:
                stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
            yield AgentEvent(
                actor_key=self.target.key,
                role="system",
                event_type="error",
                content=f"Claude Code exited with {exit_code}.\n{stderr.strip()}",
                meta={"exit_code": exit_code},
                is_final=True,
            )

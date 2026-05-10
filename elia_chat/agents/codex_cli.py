from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator

from elia_chat.agents.base import AgentEvent, AgentTarget
from elia_chat.agents.parsers import codex_event, parse_json_line
from elia_chat.agents.prompts import build_group_prompt


class CodexCliAgent:
    def __init__(
        self, cwd: Path | None = None, resume_thread_id: str | None = None
    ) -> None:
        command = os.getenv("CAFEDELIA_CODEX_COMMAND", "codex")
        self.cwd = cwd or Path.cwd()
        if resume_thread_id:
            command_parts = [
                command,
                "exec",
                "resume",
                "--json",
                "--skip-git-repo-check",
                "--dangerously-bypass-approvals-and-sandbox",
                resume_thread_id,
            ]
        else:
            command_parts = [
                command,
                "exec",
                "--json",
                "--skip-git-repo-check",
                "--dangerously-bypass-approvals-and-sandbox",
            ]
        self.target = AgentTarget(
            key="codex",
            name="Codex",
            command=command_parts,
        )

    async def run(
        self,
        prompt: str,
        *,
        transcript: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        grouped_prompt = build_group_prompt(
            agent_name="Codex",
            peer_name="Claude Code",
            user_prompt=prompt,
            transcript=transcript,
        )
        command = [*self.target.command, grouped_prompt]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
        )

        seen_messages: set[str] = set()
        assert process.stdout is not None
        async for line in process.stdout:
            parsed = parse_json_line(line)
            if parsed is None:
                continue
            event = codex_event(self.target.key, parsed)
            if event is None:
                continue
            if event.event_type == "message" and event.content in seen_messages:
                continue
            seen_messages.add(event.content)
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
                content=f"Codex exited with {exit_code}.\n{stderr.strip()}",
                meta={"exit_code": exit_code},
                is_final=True,
            )

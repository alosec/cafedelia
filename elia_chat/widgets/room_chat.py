from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from elia_chat.agents.base import AgentAdapter, AgentEvent
from elia_chat.agents.claude_code import ClaudeCodeAgent
from elia_chat.agents.codex_cli import CodexCliAgent
from elia_chat.rooms.manager import RoomManager, RoomMessageData
from elia_chat.rooms.routing import parse_recipients
from elia_chat.widgets.agent_is_typing import ResponseStatus
from elia_chat.widgets.prompt_input import PromptInput
from elia_chat.widgets.room_message import RoomMessageWidget


class RoomPromptInput(PromptInput):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close room", key_display="esc")]

    def on_mount(self):
        self.border_title = "Message room..."


class RoomChat(Widget):
    allow_input_submit = reactive(True)

    @dataclass
    class NewRoomMessage(Message):
        content: str
        recipients: tuple[str, ...]

    def __init__(self, room_id: int, title: str, startup_prompt: str = "") -> None:
        super().__init__()
        self.room_id = room_id
        self.title = title
        self.startup_prompt = startup_prompt

    def compose(self) -> ComposeResult:
        yield ResponseStatus()
        yield Static(
            f"[b]Cafedelia Room[/] · {self.title}\n"
            "[dim]Mention @claude or @codex to route one agent; default sends to both.[/]",
            id="room-header",
        )
        with VerticalScroll(id="room-container") as vertical_scroll:
            vertical_scroll.can_focus = False
        yield RoomPromptInput(id="room-prompt")

    async def on_mount(self, _: events.Mount) -> None:
        await self.load_room()
        if self.startup_prompt:
            await self.submit_text(self.startup_prompt)

    @property
    def room_container(self) -> VerticalScroll:
        return self.query_one("#room-container", VerticalScroll)

    async def load_room(self) -> None:
        messages = await RoomManager.get_messages(self.room_id)
        await self.room_container.mount_all(
            [RoomMessageWidget(message) for message in messages]
        )
        self.room_container.scroll_end(animate=False, force=True)

    @on(PromptInput.PromptSubmitted)
    async def handle_prompt(self, event: PromptInput.PromptSubmitted) -> None:
        if not self.allow_input_submit:
            self.app.bell()
            self.notify("Please wait for agent responses to complete.")
            return

        text = event.text.strip()
        await self.submit_text(text)

    async def submit_text(self, text: str) -> None:
        recipients = parse_recipients(text)
        message = await RoomManager.add_message(
            self.room_id,
            "user",
            text,
            role="user",
            event_type="message",
            meta={"recipients": list(recipients)},
        )
        await self.mount_room_message(message)
        self.post_message(self.NewRoomMessage(text, recipients))
        self.dispatch_agents(text, recipients)

    async def mount_room_message(self, message: RoomMessageData) -> None:
        await self.room_container.mount(RoomMessageWidget(message))
        self.room_container.scroll_end(animate=False, force=True)

    @work(exclusive=True, group="room-agents")
    async def dispatch_agents(self, text: str, recipients: tuple[str, ...]) -> None:
        self.allow_input_submit = False
        prompt = self.query_one(RoomPromptInput)
        prompt.submit_ready = False
        response_status = self.query_one(ResponseStatus)
        response_status.set_agent_responding()
        response_status.display = True

        transcript = await RoomManager.format_transcript(self.room_id)
        adapters = await self.build_adapters(recipients)
        try:
            await asyncio.gather(
                *(self.run_agent(adapter, text, transcript) for adapter in adapters)
            )
        finally:
            response_status.display = False
            prompt.submit_ready = True
            self.allow_input_submit = True

    async def build_adapters(self, recipients: tuple[str, ...]) -> list[AgentAdapter]:
        cwd = Path.cwd()
        adapters: list[AgentAdapter] = []
        if "claude" in recipients:
            resume_session_id = await RoomManager.latest_actor_meta_value(
                self.room_id,
                "claude",
                "session_id",
            )
            adapters.append(ClaudeCodeAgent(cwd, resume_session_id=resume_session_id))
        if "codex" in recipients:
            resume_thread_id = await RoomManager.latest_actor_meta_value(
                self.room_id,
                "codex",
                "thread_id",
            )
            adapters.append(CodexCliAgent(cwd, resume_thread_id=resume_thread_id))
        return adapters

    async def run_agent(
        self,
        adapter: AgentAdapter,
        text: str,
        transcript: str,
    ) -> None:
        run = await RoomManager.create_agent_run(
            self.room_id,
            adapter.target.key,
            adapter.target.command,
        )
        try:
            async for event in adapter.run(text, transcript=transcript):
                await self.persist_and_mount_event(event)
            await RoomManager.finish_agent_run(run.id, status="completed", exit_code=0)
        except FileNotFoundError as error:
            await RoomManager.finish_agent_run(
                run.id, status="failed", error=str(error)
            )
            await self.persist_and_mount_event(
                AgentEvent(
                    actor_key=adapter.target.key,
                    role="system",
                    event_type="error",
                    content=f"Command not found: `{adapter.target.command[0]}`",
                    meta={"error": str(error)},
                    is_final=True,
                )
            )
        except Exception as error:
            await RoomManager.finish_agent_run(
                run.id, status="failed", error=str(error)
            )
            await self.persist_and_mount_event(
                AgentEvent(
                    actor_key=adapter.target.key,
                    role="system",
                    event_type="error",
                    content=str(error),
                    meta={"error": str(error)},
                    is_final=True,
                )
            )

    async def persist_and_mount_event(self, event: AgentEvent) -> None:
        message = await RoomManager.add_message(
            self.room_id,
            event.actor_key,
            event.content,
            role=event.role,
            event_type=event.event_type,
            raw_json=event.raw_json,
            meta=event.meta,
        )
        await self.mount_room_message(message)

    @on(PromptInput.CursorEscapingBottom)
    async def move_focus_below(self) -> None:
        try:
            self.query(RoomMessageWidget).last().focus()
        except Exception:
            pass

    @on(RoomMessageWidget.CursorEscapingBottom)
    def move_focus_to_prompt(self) -> None:
        self.query_one(RoomPromptInput).focus()

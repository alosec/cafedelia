from __future__ import annotations

from rich.console import RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget

from elia_chat.rooms.manager import RoomMessageData


class RoomMessageWidget(Widget, can_focus=True):
    BINDINGS = [
        Binding("up,k", "up", "Up", show=False),
        Binding("down,j", "down", "Down", show=False),
        Binding(
            "escape", "screen.focus('room-prompt')", "Focus prompt", key_display="esc"
        ),
    ]

    class CursorEscapingBottom(Message):
        pass

    def __init__(self, message: RoomMessageData) -> None:
        super().__init__(classes=f"room-{message.actor_key} room-{message.event_type}")
        self.message = message

    def action_up(self) -> None:
        self.screen.focus_previous(RoomMessageWidget)

    def action_down(self) -> None:
        if self.parent and self is self.parent.children[-1]:
            self.post_message(self.CursorEscapingBottom())
        else:
            self.screen.focus_next(RoomMessageWidget)

    def render(self) -> RenderableType:
        title = self.message.actor_name
        if self.message.event_type != "message":
            title = f"{title} · {self.message.event_type}"

        border_style = {
            "user": "white",
            "claude": "magenta",
            "codex": "cyan",
            "system": "yellow",
        }.get(self.message.actor_key, "blue")

        if self.message.event_type == "error":
            border_style = "red"
        elif self.message.event_type in {"tool_call", "tool_result"}:
            border_style = "green"

        if self.message.actor_key == "user":
            body = Syntax(
                self.message.content,
                lexer="markdown",
                word_wrap=True,
                background_color="#121212",
            )
        else:
            body = Markdown(
                self.message.content,
                code_theme=self.app.launch_config.message_code_theme,
            )

        return Panel(body, title=title, border_style=border_style, padding=(0, 1))

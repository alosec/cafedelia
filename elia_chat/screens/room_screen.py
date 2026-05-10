from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer

from elia_chat.widgets.room_chat import RoomChat


class RoomScreen(Screen[None]):
    AUTO_FOCUS = "RoomPromptInput"
    BINDINGS = [
        Binding(
            key="escape",
            action="app.focus('room-prompt')",
            description="Focus prompt",
            key_display="esc",
        ),
    ]

    def __init__(self, room_id: int, title: str, startup_prompt: str = ""):
        super().__init__()
        self.room_id = room_id
        self.title = title
        self.startup_prompt = startup_prompt

    def compose(self) -> ComposeResult:
        yield RoomChat(self.room_id, self.title, self.startup_prompt)
        yield Footer()

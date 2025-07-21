from __future__ import annotations

import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App
from textual.binding import Binding
from textual.reactive import Reactive, reactive
from textual.signal import Signal

from elia_chat.chats_manager import ChatsManager
from elia_chat.models import ChatData, ChatMessage
from elia_chat.config import EliaChatModel, LaunchConfig
from elia_chat.runtime_config import RuntimeConfig
from elia_chat.screens.chat_screen import ChatScreen
from elia_chat.screens.help_screen import HelpScreen
from elia_chat.screens.home_screen import HomeScreen
from elia_chat.screens.sync_manager_screen import SyncManagerScreen
from elia_chat.themes import BUILTIN_THEMES, Theme, load_user_themes

if TYPE_CHECKING:
    from litellm.types.completion import (
        ChatCompletionUserMessageParam,
        ChatCompletionSystemMessageParam,
    )


class Elia(App[None]):
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = Path(__file__).parent / "elia.scss"
    BINDINGS = [
        Binding("q", "app.quit", "Quit", show=False),
        Binding("f1,?", "help", "Help"),
        Binding("f9", "sync_manager", "Sync Manager", show=False),
    ]

    def __init__(self, config: LaunchConfig, startup_prompt: str = ""):
        self.launch_config = config

        available_themes: dict[str, Theme] = BUILTIN_THEMES.copy()
        available_themes |= load_user_themes()

        self.themes: dict[str, Theme] = available_themes

        self._runtime_config = RuntimeConfig(
            selected_model=config.default_model_object,
            system_prompt=config.system_prompt,
        )
        
        # Initialize WTE pipeline server
        self.wte_server = None
        self.runtime_config_signal = Signal[RuntimeConfig](
            self, "runtime-config-updated"
        )
        """Widgets can subscribe to this signal to be notified of
        when the user has changed configuration at runtime (e.g. using the UI)."""

        self.startup_prompt = startup_prompt
        """Elia can be launched with a prompt on startup via a command line option.

        This is a convenience which will immediately load the chat interface and
        put users into the chat window, rather than going to the home screen.
        """

        super().__init__()

    theme: Reactive[str | None] = reactive(None, init=False)

    @property
    def runtime_config(self) -> RuntimeConfig:
        return self._runtime_config

    @runtime_config.setter
    def runtime_config(self, new_runtime_config: RuntimeConfig) -> None:
        self._runtime_config = new_runtime_config
        self.runtime_config_signal.publish(self.runtime_config)

    async def on_mount(self) -> None:
        # Initialize WTE pipeline server for modern sync architecture
        try:
            from sync.wte.simple_manager import SimpleWTEServer
            
            self.wte_server = SimpleWTEServer()
            await self.wte_server.start_server()
            self.log.info("WTE Pipeline Server started successfully")
        except Exception as e:
            # Log but don't fail if WTE server can't start
            self.log.warning(f"Could not start WTE pipeline server: {e}")
            
            # Fallback to legacy sync service
            try:
                from sync.service import sync_service
                await sync_service.start()
                self.log.info("Fallback to legacy sync service")
            except Exception as fallback_e:
                self.log.warning(f"Legacy sync service also failed: {fallback_e}")
        
        await self.push_screen(HomeScreen(self.runtime_config_signal))
        self.theme = self.launch_config.theme
        if self.startup_prompt:
            await self.launch_chat(
                prompt=self.startup_prompt,
                model=self.runtime_config.selected_model,
            )

    async def launch_chat(self, prompt: str, model: EliaChatModel) -> None:
        current_time = datetime.datetime.now(datetime.timezone.utc)
        system_message: ChatCompletionSystemMessageParam = {
            "content": self.runtime_config.system_prompt,
            "role": "system",
        }
        user_message: ChatCompletionUserMessageParam = {
            "content": prompt,
            "role": "user",
        }
        chat = ChatData(
            id=None,
            title=None,
            create_timestamp=None,
            model=model,
            messages=[
                ChatMessage(
                    message=system_message,
                    timestamp=current_time,
                    model=model,
                ),
                ChatMessage(
                    message=user_message,
                    timestamp=current_time,
                    model=model,
                ),
            ],
            session_id=None,  # Explicitly set to None for non-Claude Code sessions
        )
        chat.id = await ChatsManager.create_chat(chat_data=chat)
        await self.push_screen(ChatScreen(chat))

    async def action_help(self) -> None:
        if isinstance(self.screen, HelpScreen):
            self.pop_screen()
        else:
            await self.push_screen(HelpScreen())
    
    async def action_sync_manager(self) -> None:
        """Open the WTE pipeline sync manager"""
        if self.wte_server:
            await self.push_screen(SyncManagerScreen(self.wte_server))
        else:
            self.notify("WTE Pipeline Server not available", severity="error")

    def get_css_variables(self) -> dict[str, str]:
        if self.theme:
            theme = self.themes.get(self.theme)
            if theme:
                color_system = theme.to_color_system().generate()
            else:
                color_system = {}
        else:
            color_system = {}

        return {**super().get_css_variables(), **color_system}

    def watch_theme(self, theme: str | None) -> None:
        self.refresh_css(animate=False)
        self.screen._update_styles()

    @property
    def theme_object(self) -> Theme | None:
        try:
            return self.themes[self.theme]
        except KeyError:
            return None
    
    async def on_shutdown(self) -> None:
        """Clean shutdown of sync service."""
        try:
            from sync.service import sync_service
            await sync_service.stop()
        except Exception as e:
            self.log.warning(f"Error stopping sync service: {e}")


if __name__ == "__main__":
    app = Elia(LaunchConfig())
    app.run()

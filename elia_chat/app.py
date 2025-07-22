from __future__ import annotations

import asyncio
import datetime
import subprocess
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
from elia_chat.themes import BUILTIN_THEMES, Theme, load_user_themes
from bridge.session_sync import get_session_sync, close_global_sync

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
    ]

    def __init__(self, config: LaunchConfig, startup_prompt: str = ""):
        self.cafed_enabled = True  # TODO: Make this configurable
        self.launch_config = config

        available_themes: dict[str, Theme] = BUILTIN_THEMES.copy()
        available_themes |= load_user_themes()

        self.themes: dict[str, Theme] = available_themes

        self._runtime_config = RuntimeConfig(
            selected_model=config.default_model_object,
            system_prompt=config.system_prompt,
        )
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

    async def start_cafed_backend(self) -> bool:
        """Start the cafed backend server or connect to existing one"""
        if not self.cafed_enabled:
            return True
            
        try:
            # First check if backend is already running by testing the health endpoint
            session_sync = get_session_sync()
            try:
                health = await session_sync.health_check()
                if health.get('overall_status') == 'ok':
                    # Backend is already running, sync sessions
                    sync_results = await session_sync.sync_all_sessions()
                    created_count = sync_results.get('created', 0)
                    updated_count = sync_results.get('updated', 0)
                    
                    if created_count > 0 or updated_count > 0:
                        self.notify(f"Connected to backend - synced {created_count} new, {updated_count} updated Claude sessions", severity="information")
                    else:
                        self.notify("Connected to cafed backend successfully", severity="information")
                    return True
            except:
                # Backend not running, try to start it
                pass
            
            # Get the project root directory
            project_root = Path(__file__).parent.parent
            cafed_script = project_root / "scripts" / "start-cafed.sh"
            
            if not cafed_script.exists():
                self.notify("Cafed backend not found. Continuing without session management.", severity="warning")
                self.cafed_enabled = False
                return False
            
            # Start cafed backend with Docker
            start_result = subprocess.run(
                [str(cafed_script), "production"],
                capture_output=True,
                text=True,
                cwd=project_root
            )
            
            # The script returns 0 whether it starts a new container or finds one already running
            if start_result.returncode != 0:
                self.notify(f"Failed to start cafed backend: {start_result.stderr}", severity="error")
                return False
            
            # Give Docker containers time to be ready
            await asyncio.sleep(3)
            
            # Try to connect and sync sessions
            try:
                health = await session_sync.health_check()
                if health.get('overall_status') == 'ok':
                    # Sync live sessions into chat database
                    sync_results = await session_sync.sync_all_sessions()
                    created_count = sync_results.get('created', 0)
                    updated_count = sync_results.get('updated', 0)
                    
                    if created_count > 0 or updated_count > 0:
                        self.notify(f"Backend started - synced {created_count} new, {updated_count} updated Claude sessions", severity="information")
                    else:
                        self.notify("Cafed backend started successfully", severity="information")
                    return True
                else:
                    self.notify("Cafed backend started but health check failed", severity="warning")
                    return False
            except Exception as e:
                self.notify(f"Cafed backend started but sync failed: {e}", severity="warning")
                return False
                
        except Exception as e:
            self.notify(f"Failed to start cafed backend: {e}", severity="error")
            self.cafed_enabled = False
            return False

    async def stop_cafed_backend(self) -> None:
        """Stop the cafed backend server"""
        try:
            # Only stop containers if we're enabled - don't interfere with external Docker management
            if not self.cafed_enabled:
                await close_global_sync()
                return
                
            # Use Docker compose to stop containers properly
            project_root = Path(__file__).parent.parent
            stop_result = subprocess.run(
                ["docker", "compose", "down"],
                cwd=project_root,
                capture_output=True,
                text=True
            )
            
            if stop_result.returncode != 0:
                self.notify(f"Warning: Docker stop had issues: {stop_result.stderr}", severity="warning")
                    
        except Exception as e:
            self.notify(f"Error stopping cafed backend: {e}", severity="warning")
        
        # Close bridge connections
        await close_global_sync()

    async def on_mount(self) -> None:
        # Start cafed backend first
        if self.cafed_enabled:
            await self.start_cafed_backend()
        
        await self.push_screen(HomeScreen(self.runtime_config_signal))
        self.theme = self.launch_config.theme
        if self.startup_prompt:
            await self.launch_chat(
                prompt=self.startup_prompt,
                model=self.runtime_config.selected_model,
            )

    async def on_unmount(self) -> None:
        """Clean up when app is shutting down"""
        await self.stop_cafed_backend()

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
        )
        chat.id = await ChatsManager.create_chat(chat_data=chat)
        await self.push_screen(ChatScreen(chat))

    async def action_help(self) -> None:
        if isinstance(self.screen, HelpScreen):
            self.pop_screen()
        else:
            await self.push_screen(HelpScreen())

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


if __name__ == "__main__":
    app = Elia(LaunchConfig())
    app.run()

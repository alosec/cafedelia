from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Self, cast

import humanize
from rich.console import RenderResult, Console, ConsoleOptions
from rich.markup import escape
from rich.padding import Padding
from rich.text import Text
from textual import events, log, on
from textual.binding import Binding
from textual.geometry import Region
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from elia_chat.chats_manager import ChatsManager
from elia_chat.config import LaunchConfig
from elia_chat.models import ChatData
from elia_chat.widgets.pagination_mixin import PaginationMixin, PaginatedDataSource


@dataclass
class ChatListItemRenderable:
    chat: ChatData
    config: LaunchConfig

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = now - self.chat.update_time
        time_ago = humanize.naturaltime(delta)
        time_ago_text = Text(time_ago, style="dim i")
        model = self.chat.model
        subtitle = f"[dim]{escape(model.display_name or model.name)}"
        if model.provider:
            subtitle += f" [i]by[/] {escape(model.provider)}"
        model_text = Text.from_markup(subtitle)
        title = self.chat.title or self.chat.short_preview.replace("\n", " ")
        yield Padding(
            Text.assemble(title, "\n", model_text, "\n", time_ago_text),
            pad=(0, 0, 0, 1),
        )


class ChatListItem(Option):
    def __init__(self, chat: ChatData, config: LaunchConfig) -> None:
        """
        Args:
            chat: The chat associated with this option.
        """
        super().__init__(ChatListItemRenderable(chat, config))
        self.chat = chat
        self.config = config


class ChatDataSource:
    """Data source adapter for ChatsManager to work with pagination."""
    
    async def get_page(self, limit: int, offset: int) -> list[ChatData]:
        """Get a page of chat data."""
        return await ChatsManager.paginated_chats(limit=limit, offset=offset)
    
    async def get_total_count(self) -> int:
        """Get total count of chats."""
        return await ChatsManager.count_chats()


class ChatList(OptionList, PaginationMixin[ChatData]):
    BINDINGS = [
        Binding(
            "escape",
            "app.focus('home-prompt')",
            "Focus prompt",
            key_display="esc",
            tooltip="Return focus to the prompt input.",
        ),
        Binding(
            "a",
            "archive_chat",
            "Archive chat",
            key_display="a",
            tooltip="Archive the highlighted chat"
            " (without deleting it from Elia's database).",
        ),
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
        Binding("l,right,enter", "select", "Select", show=False),
        Binding("g,home", "first", "First", show=False),
        Binding("G,end", "last", "Last", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
    ]

    def __init__(self, **kwargs):
        OptionList.__init__(self, **kwargs)
        PaginationMixin.__init__(self, page_size=50, preload_pages=2)
        self._data_source_configured = False

    @dataclass
    class ChatOpened(Message):
        chat: ChatData

    class CursorEscapingTop(Message):
        """Cursor attempting to move out-of-bounds at top of list."""

    class CursorEscapingBottom(Message):
        """Cursor attempting to move out-of-bounds at bottom of list."""

    async def on_mount(self) -> None:
        # Configure data source now that app is available
        if not self._data_source_configured:
            data_source = ChatDataSource()
            item_factory = lambda chat: ChatListItem(chat, self.app.launch_config)
            self.set_data_source(data_source, item_factory)
            self._data_source_configured = True
        
        # Initialize pagination instead of loading all chats
        await self.initialize_pagination()

    @on(OptionList.OptionSelected)
    async def post_chat_opened(self, event: OptionList.OptionSelected) -> None:
        assert isinstance(event.option, ChatListItem)
        chat = event.option.chat
        await self.reload_and_refresh()
        self.post_message(ChatList.ChatOpened(chat=chat))

    @on(OptionList.OptionHighlighted)
    @on(events.Focus)
    async def show_border_subtitle(self) -> None:
        if self.highlighted is not None:
            self.border_subtitle = self.get_border_subtitle()
            # Check if we need to load more data for infinite scroll
            await self.handle_scroll_near_end(self.highlighted)
        elif self.option_count > 0:
            self.highlighted = 0

    def on_blur(self) -> None:
        self.border_subtitle = None

    async def reload_and_refresh(self, new_highlighted: int = -1) -> None:
        """Reload the chats and refresh the widget with pagination.

        Args:
            new_highlighted: The index to highlight after refresh.
        """
        old_highlighted = self.highlighted
        
        # Clear existing data and reset pagination
        self.clear_options()
        self.loaded_pages.clear()
        self.loading_pages.clear()
        self.all_loaded = False
        self.current_page = 0
        
        # Reinitialize pagination
        await self.initialize_pagination()
        
        self.border_title = self.get_border_title()
        if new_highlighted > -1:
            self.highlighted = new_highlighted
        else:
            self.highlighted = old_highlighted

        self.refresh()

    async def load_chat_list_items(self) -> list[ChatListItem]:
        """Legacy method - now handled by pagination."""
        log.warning("load_chat_list_items called - should use pagination instead")
        return []

    async def load_chats(self) -> list[ChatData]:
        """Legacy method - now handled by pagination.""" 
        log.warning("load_chats called - should use pagination instead")
        return []

    async def action_archive_chat(self) -> None:
        if self.highlighted is None:
            return

        item = cast(ChatListItem, self.get_option_at_index(self.highlighted))
        self.remove_option_at_index(self.highlighted)

        chat_id = item.chat.id
        await ChatsManager.archive_chat(chat_id)

        self.border_title = self.get_border_title()
        self.border_subtitle = self.get_border_subtitle()
        self.app.notify(
            item.chat.title or f"Chat [b]{chat_id!r}[/] archived.",
            title="Chat archived",
        )
        self.refresh()

    def get_border_title(self) -> str:
        loaded_count = self.option_count
        if self.total_items > 0:
            if self.all_loaded:
                return f"History ({loaded_count} of {self.total_items})"
            else:
                return f"History ({loaded_count} of {self.total_items}+)"
        else:
            return f"History ({loaded_count})"

    def get_border_subtitle(self) -> str:
        if self.highlighted is None:
            return ""
        return f"{self.highlighted + 1} / {self.option_count}"

    def create_chat(self, chat_data: ChatData) -> None:
        new_chat_list_item = ChatListItem(chat_data, self.app.launch_config)
        log.debug(f"Creating new chat {new_chat_list_item!r}")

        # Store existing options before clearing
        existing_options = [self.get_option_at_index(i) for i in range(self.option_count)]
        
        # Clear and rebuild with new chat at top
        self.clear_options()
        self.add_option(new_chat_list_item)
        self.add_options(existing_options)
        self.highlighted = 0
        self.refresh()

    def action_cursor_up(self) -> None:
        if self.highlighted == 0:
            self.post_message(self.CursorEscapingTop())
        else:
            return super().action_cursor_up()

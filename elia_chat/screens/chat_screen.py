from textual import on, log
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer

from elia_chat.chats_manager import ChatsManager
from elia_chat.widgets.agent_is_typing import ResponseStatus
from elia_chat.widgets.chat import Chat
from elia_chat.widgets.chat_header import ChatHeader
from elia_chat.widgets.session_log_viewer import SessionLogViewer
from elia_chat.models import ChatData


class ChatScreen(Screen[None]):
    AUTO_FOCUS = "ChatPromptInput"
    BINDINGS = [
        Binding(
            key="escape",
            action="app.focus('prompt')",
            description="Focus prompt",
            key_display="esc",
            tooltip="Return focus to the prompt input.",
        ),
        Binding(
            key="f3",
            action="toggle_logs",
            description="Toggle logs",
            key_display="F3",
            tooltip="Show/hide session logs panel.",
        ),
    ]

    def __init__(
        self,
        chat_data: ChatData,
    ):
        super().__init__()
        self.chat_data = chat_data
        self.chats_manager = ChatsManager()
        self._log_viewer_visible = self._should_show_logs_by_default()

    def compose(self) -> ComposeResult:
        if self._log_viewer_visible:
            with Horizontal():
                chat = Chat(self.chat_data)
                chat.id = "main-chat"
                yield chat
                log_viewer = SessionLogViewer()
                log_viewer.id = "session-logs"
                # Set session ID immediately if available
                if self.chat_data.session_id:
                    log_viewer.session_id = self.chat_data.session_id
                yield log_viewer
        else:
            chat = Chat(self.chat_data)
            chat.id = "main-chat"
            yield chat
        yield Footer()

    @on(Chat.NewUserMessage)
    def new_user_message(self, event: Chat.NewUserMessage) -> None:
        """Handle a new user message."""
        self.query_one(Chat).allow_input_submit = False
        response_status = self.query_one(ResponseStatus)
        response_status.set_awaiting_response()
        response_status.display = True

    @on(Chat.AgentResponseStarted)
    def start_awaiting_response(self) -> None:
        """Prevent sending messages because the agent is typing."""
        response_status = self.query_one(ResponseStatus)
        response_status.set_agent_responding()
        response_status.display = True

    @on(Chat.AgentResponseComplete)
    async def agent_response_complete(self, event: Chat.AgentResponseComplete) -> None:
        """Allow the user to send messages again."""
        self.query_one(ResponseStatus).display = False
        self.query_one(Chat).allow_input_submit = True
        log.debug(
            f"Agent response complete. Adding message "
            f"to chat_id {event.chat_id!r}: {event.message}"
        )
        if self.chat_data.id is None:
            raise RuntimeError("Chat has no ID. This is likely a bug in Elia.")

        await self.chats_manager.add_message_to_chat(
            chat_id=self.chat_data.id, message=event.message
        )
    
    def _should_show_logs_by_default(self) -> bool:
        """Determine if logs should be shown by default for this chat."""
        # Show logs for chats that have a session_id (Claude Code sessions)
        return self.chat_data.session_id is not None
    
    def action_toggle_logs(self) -> None:
        """Toggle the session logs panel."""
        self._log_viewer_visible = not self._log_viewer_visible
        self.refresh(recompose=True)
        
        # If we're showing logs and have a session ID, start tailing
        if self._log_viewer_visible:
            self._update_log_viewer_session()
    
    def _update_log_viewer_session(self) -> None:
        """Update the log viewer with the current session ID."""
        try:
            log_viewer = self.query_one(SessionLogViewer)
            # Use session_id directly from chat_data
            if self.chat_data.session_id:
                log_viewer.session_id = self.chat_data.session_id
            
        except Exception as e:
            log.warning(f"Could not update log viewer session: {e}")
    
    @on(Chat.AgentResponseStarted)
    def on_claude_session_started(self, event: Chat.AgentResponseStarted) -> None:
        """Handle Claude Code session start for log tailing."""
        if self._log_viewer_visible:
            # Small delay to ensure session ID is captured
            self.call_later(self._update_log_viewer_session)
    
    @on(Chat.SessionIdCaptured)
    def on_session_id_captured(self, event: Chat.SessionIdCaptured) -> None:
        """Handle Claude Code session ID capture for log tailing."""
        if self._log_viewer_visible:
            try:
                log_viewer = self.query_one(SessionLogViewer)
                log_viewer.session_id = event.session_id
                log.debug(f"Log viewer now tailing session: {event.session_id}")
            except Exception as e:
                log.warning(f"Could not update log viewer with session ID: {e}")
        
        # Update the chat header to show session ID
        try:
            chat = self.query_one("#main-chat", Chat) if self._log_viewer_visible else self.query_one(Chat)
            chat_header = chat.query_one(ChatHeader)
            chat_header.update_header(self.chat_data, self.chat_data.model)
            log.debug(f"Updated chat header with session ID: {event.session_id}")
        except Exception as e:
            log.warning(f"Could not update chat header with session ID: {e}")

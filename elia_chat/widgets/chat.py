from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from textual.widgets import Label

from elia_chat import constants
from textual import log, on, work, events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from elia_chat.chats_manager import ChatsManager
from elia_chat.models import ChatData, ChatMessage
from elia_chat.screens.chat_details import ChatDetails
from elia_chat.widgets.agent_is_typing import ResponseStatus
from elia_chat.widgets.chat_header import ChatHeader, TitleStatic
from elia_chat.widgets.prompt_input import PromptInput
from elia_chat.widgets.chatbox import Chatbox


if TYPE_CHECKING:
    from elia_chat.app import Elia
    from litellm.types.completion import (
        ChatCompletionUserMessageParam,
        ChatCompletionAssistantMessageParam,
    )


class ChatPromptInput(PromptInput):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close chat", key_display="esc")]


class Chat(Widget):
    BINDINGS = [
        Binding("ctrl+r", "rename", "Rename", key_display="^r"),
        Binding("shift+down", "scroll_container_down", show=False),
        Binding("shift+up", "scroll_container_up", show=False),
        Binding(
            key="g",
            action="focus_first_message",
            description="First message",
            key_display="g",
            show=False,
        ),
        Binding(
            key="G",
            action="focus_latest_message",
            description="Latest message",
            show=False,
        ),
        Binding(key="f2", action="details", description="Chat info"),
    ]

    allow_input_submit = reactive(True)
    """Used to lock the chat input while the agent is responding."""

    def __init__(self, chat_data: ChatData) -> None:
        super().__init__()
        self.chat_data = chat_data
        self.elia = cast("Elia", self.app)
        self.model = chat_data.model

    @dataclass
    class AgentResponseStarted(Message):
        pass

    @dataclass
    class AgentResponseComplete(Message):
        chat_id: int | None
        message: ChatMessage
        chatbox: Chatbox

    @dataclass
    class AgentResponseFailed(Message):
        """Sent when the agent fails to respond e.g. cant connect.
        Can be used to reset UI state."""

        last_message: ChatMessage

    @dataclass
    class NewUserMessage(Message):
        content: str
    
    @dataclass
    class SessionIdCaptured(Message):
        """Sent when a Claude Code session ID is captured."""
        session_id: str

    def compose(self) -> ComposeResult:
        yield ResponseStatus()
        yield ChatHeader(chat=self.chat_data, model=self.model)

        with VerticalScroll(id="chat-container") as vertical_scroll:
            vertical_scroll.can_focus = False

        yield ChatPromptInput(id="prompt")

    async def on_mount(self, _: events.Mount) -> None:
        """
        When the component is mounted, we need to check if there is a new chat to start
        """
        await self.load_chat(self.chat_data)

    @property
    def chat_container(self) -> VerticalScroll:
        return self.query_one("#chat-container", VerticalScroll)

    @property
    def is_empty(self) -> bool:
        """True if the conversation is empty, False otherwise."""
        return len(self.chat_data.messages) == 1  # Contains system message at first.

    def scroll_to_latest_message(self):
        container = self.chat_container
        container.refresh()
        container.scroll_end(animate=False, force=True)

    @on(AgentResponseFailed)
    def restore_state_on_agent_failure(self, event: Chat.AgentResponseFailed) -> None:
        original_prompt = event.last_message.message.get("content", "")
        if isinstance(original_prompt, str):
            self.query_one(ChatPromptInput).text = original_prompt

    async def new_user_message(self, content: str) -> None:
        log.debug(f"User message submitted in chat {self.chat_data.id!r}: {content!r}")

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        user_message: ChatCompletionUserMessageParam = {
            "content": content,
            "role": "user",
        }

        user_chat_message = ChatMessage(user_message, now_utc, self.chat_data.model)
        self.chat_data.messages.append(user_chat_message)
        user_message_chatbox = Chatbox(user_chat_message, self.chat_data.model)

        assert (
            self.chat_container is not None
        ), "Textual has mounted container at this point in the lifecycle."

        await self.chat_container.mount(user_message_chatbox)

        self.scroll_to_latest_message()
        self.post_message(self.NewUserMessage(content))

        await ChatsManager.add_message_to_chat(
            chat_id=self.chat_data.id, message=user_chat_message
        )

        prompt = self.query_one(ChatPromptInput)
        prompt.submit_ready = False
        self.stream_agent_response()

    @work(thread=True, group="agent_response")
    async def stream_agent_response(self) -> None:
        model = self.chat_data.model
        log.debug(f"Creating streaming response with model {model.name!r}")

        # Check if this is a Claude Code session
        if self._is_claude_code_session():
            await self._stream_claude_code_response()
            return

        import litellm
        from litellm import ModelResponse, acompletion
        from litellm.utils import trim_messages

        raw_messages = [message.message for message in self.chat_data.messages]

        messages: list[ChatCompletionUserMessageParam] = trim_messages(
            raw_messages, model.name
        )  # type: ignore

        litellm.organization = model.organization
        try:
            response = await acompletion(
                messages=messages,
                stream=True,
                model=model.name,
                temperature=model.temperature,
                max_retries=model.max_retries,
                api_key=model.api_key.get_secret_value() if model.api_key else None,
                api_base=model.api_base.unicode_string() if model.api_base else None,
            )
        except Exception as exception:
            self.app.notify(
                f"{exception}",
                title="Error",
                severity="error",
                timeout=constants.ERROR_NOTIFY_TIMEOUT_SECS,
            )
            self.post_message(self.AgentResponseFailed(self.chat_data.messages[-1]))
            return

        ai_message: ChatCompletionAssistantMessageParam = {
            "content": "",
            "role": "assistant",
        }
        now = datetime.datetime.now(datetime.timezone.utc)

        message = ChatMessage(message=ai_message, model=model, timestamp=now)
        response_chatbox = Chatbox(
            message=message,
            model=self.chat_data.model,
            classes="response-in-progress",
        )
        self.post_message(self.AgentResponseStarted())
        self.app.call_from_thread(self.chat_container.mount, response_chatbox)

        assert (
            self.chat_container is not None
        ), "Textual has mounted container at this point in the lifecycle."

        try:
            chunk_count = 0
            async for chunk in response:
                chunk = cast(ModelResponse, chunk)
                response_chatbox.border_title = "Agent is responding..."

                chunk_content = chunk.choices[0].delta.content
                if isinstance(chunk_content, str):
                    self.app.call_from_thread(
                        response_chatbox.append_chunk, chunk_content
                    )
                else:
                    break

                scroll_y = self.chat_container.scroll_y
                max_scroll_y = self.chat_container.max_scroll_y
                if scroll_y in range(max_scroll_y - 3, max_scroll_y + 1):
                    self.app.call_from_thread(
                        self.chat_container.scroll_end, animate=False
                    )

                chunk_count += 1
        except Exception:
            self.notify(
                "There was a problem using this model. "
                "Please check your configuration file.",
                title="Error",
                severity="error",
                timeout=constants.ERROR_NOTIFY_TIMEOUT_SECS,
            )
            self.post_message(self.AgentResponseFailed(self.chat_data.messages[-1]))
        else:
            self.post_message(
                self.AgentResponseComplete(
                    chat_id=self.chat_data.id,
                    message=response_chatbox.message,
                    chatbox=response_chatbox,
                )
            )

    @on(AgentResponseFailed)
    @on(AgentResponseStarted)
    async def agent_started_responding(
        self, event: AgentResponseFailed | AgentResponseStarted
    ) -> None:
        try:
            awaiting_reply = self.chat_container.query_one("#awaiting-reply", Label)
        except NoMatches:
            pass
        else:
            if awaiting_reply:
                await awaiting_reply.remove()

    @on(AgentResponseComplete)
    def agent_finished_responding(self, event: AgentResponseComplete) -> None:
        # Ensure the thread is updated with the message from the agent
        self.chat_data.messages.append(event.message)
        event.chatbox.border_title = "Agent"
        event.chatbox.remove_class("response-in-progress")
        prompt = self.query_one(ChatPromptInput)
        prompt.submit_ready = True

    @on(PromptInput.PromptSubmitted)
    async def user_chat_message_submitted(
        self, event: PromptInput.PromptSubmitted
    ) -> None:
        if self.allow_input_submit is True:
            user_message = event.text
            await self.new_user_message(user_message)

    @on(PromptInput.CursorEscapingTop)
    async def on_cursor_up_from_prompt(
        self, event: PromptInput.CursorEscapingTop
    ) -> None:
        self.focus_latest_message()

    @on(Chatbox.CursorEscapingBottom)
    def move_focus_to_prompt(self) -> None:
        self.query_one(ChatPromptInput).focus()

    @on(TitleStatic.ChatRenamed)
    async def handle_chat_rename(self, event: TitleStatic.ChatRenamed) -> None:
        if event.chat_id == self.chat_data.id and event.new_title:
            self.chat_data.title = event.new_title
            header = self.query_one(ChatHeader)
            header.update_header(self.chat_data, self.model)
            await ChatsManager.rename_chat(event.chat_id, event.new_title)

    def get_latest_chatbox(self) -> Chatbox:
        return self.query(Chatbox).last()

    def focus_latest_message(self) -> None:
        try:
            self.get_latest_chatbox().focus()
        except NoMatches:
            pass

    def action_rename(self) -> None:
        title_static = self.query_one(TitleStatic)
        title_static.begin_rename()

    def action_focus_latest_message(self) -> None:
        self.focus_latest_message()

    def action_focus_first_message(self) -> None:
        try:
            self.query(Chatbox).first().focus()
        except NoMatches:
            pass

    def action_scroll_container_up(self) -> None:
        if self.chat_container:
            self.chat_container.scroll_up()

    def action_scroll_container_down(self) -> None:
        if self.chat_container:
            self.chat_container.scroll_down()

    async def action_details(self) -> None:
        await self.app.push_screen(ChatDetails(self.chat_data))

    def _is_claude_code_session(self) -> bool:
        """Check if this is a Claude Code session."""
        # Check if model provider is Claude Code
        if hasattr(self.model, 'provider') and self.model.provider == "Claude Code":
            return True
        
        # Check if chat title contains session ID pattern
        if self.chat_data.title and len(self.chat_data.title.split('-')) >= 5:
            # Looks like a UUID pattern
            return True
        
        # Check if chat metadata indicates Claude Code session
        if hasattr(self.chat_data, 'meta') and self.chat_data.meta:
            return 'session_id' in self.chat_data.meta
        
        return False
    
    def _extract_claude_session_id(self) -> str:
        """Extract Claude Code session ID from chat data."""
        # Try to extract from metadata first
        if hasattr(self.chat_data, 'meta') and self.chat_data.meta:
            session_id = self.chat_data.meta.get('session_id')
            if session_id:
                return session_id
        
        # Try to extract from chat ID if it looks like a UUID
        if isinstance(self.chat_data.id, str) and len(self.chat_data.id.split('-')) >= 5:
            return self.chat_data.id
        
        # Fallback: try to extract from title
        if self.chat_data.title:
            parts = self.chat_data.title.split()
            for part in parts:
                if len(part.split('-')) >= 5:  # UUID-like pattern
                    return part
        
        # If no session ID found, this might be a new session
        return str(self.chat_data.id) if self.chat_data.id else "new"
    
    async def _stream_claude_code_response(self) -> None:
        """Handle streaming response from Claude Code SDK."""
        try:
            from sync.claude_process import session_manager
            from sync.streaming_message_grouper import StreamingMessageGrouper
            
            # Get session ID and determine if we should resume
            session_id = self._extract_claude_session_id()
            should_resume = session_id != "new" and session_id != str(self.chat_data.id)
            
            log.debug(f"Streaming Claude Code response for session: {session_id} (resume: {should_resume})")
            
            # Get the last user message
            user_message = self.chat_data.messages[-1].message.get("content", "")
            if not user_message:
                log.error("No user message content found")
                self.post_message(self.AgentResponseFailed(self.chat_data.messages[-1]))
                return
            
            # Get or create session with current project path
            project_path = str(Path.cwd())  # Use current directory as project path
            model_choice = None
            if hasattr(self.model, 'cli_model'):
                model_choice = self.model.cli_model
            
            actual_session_id = await session_manager.get_or_create_session(
                session_id if should_resume else None, 
                project_path,
                model=model_choice
            )
            
            # Emit session ID for log viewer
            if actual_session_id:
                self.post_message(self.SessionIdCaptured(actual_session_id))
            
            # Create response message
            ai_message: ChatCompletionAssistantMessageParam = {
                "content": "",
                "role": "assistant",
            }
            now = datetime.datetime.now(datetime.timezone.utc)
            
            message = ChatMessage(message=ai_message, model=self.model, timestamp=now)
            response_chatbox = Chatbox(
                message=message,
                model=self.chat_data.model,
                classes="response-in-progress",
            )
            self.post_message(self.AgentResponseStarted())
            self.app.call_from_thread(self.chat_container.mount, response_chatbox)
            
            # Initialize streaming message grouper for coherent UX
            grouper = StreamingMessageGrouper()
            response_content = ""
            message_count = 0
            
            # Extract model selection from chat model
            model_choice = None
            if hasattr(self.model, 'cli_model'):
                model_choice = self.model.cli_model
                log.debug(f"Using Claude Code model: {model_choice}")
            
            async for claude_response in session_manager.send_message(
                actual_session_id, 
                user_message, 
                resume=should_resume,
                model=model_choice
            ):
                message_count += 1
                
                # Handle system messages immediately
                if claude_response.message_type == "system":
                    if "Session initialized" in claude_response.content:
                        response_chatbox.border_title = "Claude Code initializing..."
                        # Update session ID from system message
                        actual_session_id = claude_response.session_id
                        
                        # Emit updated session ID
                        if actual_session_id:
                            self.post_message(self.SessionIdCaptured(actual_session_id))
                    continue
                
                # Process response through grouper for coherent display
                grouped_message = grouper.add_response(claude_response)
                
                if grouped_message:
                    # Complete grouped message ready for display
                    if grouped_message.message_type == "system":
                        # System messages display immediately
                        self.app.call_from_thread(
                            response_chatbox.set_grouped_content, 
                            grouped_message.content, 
                            grouped_message.metadata
                        )
                    
                    elif grouped_message.message_type == "assistant":
                        # Grouped assistant content with tool calls/results
                        response_chatbox.border_title = "Claude Code"
                        self.app.call_from_thread(
                            response_chatbox.set_grouped_content,
                            grouped_message.content,
                            grouped_message.metadata
                        )
                        response_content = grouped_message.content
                    
                    elif grouped_message.message_type == "result":
                        # Final result message - log completion and break
                        metadata = grouped_message.metadata
                        if metadata.get('total_cost_usd'):
                            log.info(f"Claude Code session {actual_session_id} completed. "
                                   f"Cost: ${metadata['total_cost_usd']:.4f}, "
                                   f"Turns: {metadata.get('num_turns', 0)}, "
                                   f"Duration: {metadata.get('duration_ms', 0)}ms")
                        break
                
                else:
                    # Still building group - update status
                    if claude_response.message_type == "assistant":
                        response_chatbox.border_title = "Claude Code is responding..."
                    elif claude_response.message_type == "result":
                        response_chatbox.border_title = "Claude Code processing..."
                
                # Handle completion and errors
                if claude_response.message_type == "result" and claude_response.is_complete:
                    # Force complete any remaining group
                    final_group = grouper.force_complete_group()
                    if final_group:
                        self.app.call_from_thread(
                            response_chatbox.set_grouped_content,
                            final_group.content,
                            final_group.metadata
                        )
                        response_content = final_group.content
                    break
                
                elif claude_response.message_type == "error":
                    # Handle errors immediately
                    response_chatbox.border_title = "Claude Code Error"
                    self.app.call_from_thread(
                        response_chatbox.set_grouped_content, claude_response.content
                    )
                    break
                
                # Auto-scroll for all message types
                scroll_y = self.chat_container.scroll_y
                max_scroll_y = self.chat_container.max_scroll_y
                if scroll_y in range(max_scroll_y - 3, max_scroll_y + 1):
                    self.app.call_from_thread(
                        self.chat_container.scroll_end, animate=False
                    )
            
            # Update chat data with session ID for future reference
            if hasattr(self.chat_data, 'meta'):
                if not self.chat_data.meta:
                    self.chat_data.meta = {}
                self.chat_data.meta['session_id'] = actual_session_id
                self.chat_data.meta['claude_code_session'] = True
            
            # Ensure the message content is updated with final response
            if response_content:
                response_chatbox.message.message["content"] = response_content
            
            # Mark as complete
            self.post_message(
                self.AgentResponseComplete(
                    chat_id=self.chat_data.id,
                    message=response_chatbox.message,
                    chatbox=response_chatbox,
                )
            )
            
        except Exception as e:
            log.error(f"Error in Claude Code SDK streaming: {e}")
            self.app.notify(
                f"Claude Code SDK error: {e}",
                title="Claude Code Error",
                severity="error",
                timeout=constants.ERROR_NOTIFY_TIMEOUT_SECS,
            )
            self.post_message(self.AgentResponseFailed(self.chat_data.messages[-1]))

    async def load_chat(self, chat_data: ChatData) -> None:
        chatboxes = [
            Chatbox(chat_message, chat_data.model)
            for chat_message in chat_data.non_system_messages
        ]
        await self.chat_container.mount_all(chatboxes)
        self.chat_container.scroll_end(animate=False, force=True)
        chat_header = self.query_one(ChatHeader)
        chat_header.update_header(
            chat=chat_data,
            model=chat_data.model,
        )

        # If the last message didn't receive a response, try again.
        messages = chat_data.messages
        if messages and messages[-1].message["role"] == "user":
            prompt = self.query_one(ChatPromptInput)
            prompt.submit_ready = False
            self.stream_agent_response()

    def action_close(self) -> None:
        self.app.clear_notifications()
        self.app.pop_screen()

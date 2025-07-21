# System Patterns

## Elia Fork Architecture

### Core Extension Strategy
**Principle**: Extend Elia's proven patterns rather than replace them
- Leverage existing Textual screen management
- Extend model/provider system for CLI tools
- Preserve all API provider functionality
- Add CLI provider capabilities as new provider type

### Elia's Foundation (Inherited Strengths)

#### Screen Management Pattern
```python
# app.py - Main application with screen routing
class Elia(App[None]):
    async def on_mount(self) -> None:
        await self.push_screen(HomeScreen(self.runtime_config_signal))
    
    async def launch_chat(self, prompt: str, model: EliaChatModel) -> None:
        # Route to ChatScreen for API providers
        await self.push_screen(ChatScreen(chat))
```

**Cafedelia Extension**: Add CLI provider routing
```python
async def launch_session(self, session_id: str, model: EliaChatModel) -> None:
    if model.provider_type == "cli":
        await self.push_screen(SessionScreen(session_id, model))
    else:
        await self.launch_chat(prompt, model)  # Existing API flow
```

#### Model/Provider Configuration Pattern
```python
# config.py - EliaChatModel system
class EliaChatModel(BaseModel):
    name: str
    provider: str | None = None
    api_key: SecretStr | None = None
    # Existing API-focused fields...
```

**Cafedelia Extension**: Add CLI provider support
```python
class EliaChatModel(BaseModel):
    # Existing fields preserved...
    provider_type: Literal["api", "cli"] = "api"
    cli_command: str | None = None       # e.g. "claude code"
    session_manager: str | None = None    # e.g. "tmux" 
    session_discovery: bool = False       # Auto-detect sessions
```

#### Widget Composition Pattern
```python
# widgets/chat_options.py - Model selection interface
class OptionsModal(ModalScreen[RuntimeConfig]):
    def compose(self) -> ComposeResult:
        with RadioSet(id="available-models") as models_rs:
            for model in self.elia.launch_config.all_models:
                yield ModelRadioButton(model=model, ...)
```

**Cafedelia Extension**: Provider type separation
```python
def compose(self) -> ComposeResult:
    with RadioSet(id="provider-types") as types_rs:
        yield RadioButton("API Providers", value=True)
        yield RadioButton("CLI Providers", value=False)
    
    # Dynamic model display based on provider type
    if self.selected_provider_type == "cli":
        yield self.render_cli_providers()
    else:
        yield self.render_api_providers()  # Existing
```

### CLI Provider Architecture

#### Provider Type Abstraction
```python
# New provider type hierarchy
class BaseProvider:
    def create_session(self, config: dict) -> Session: ...
    def discover_sessions(self) -> list[SessionInfo]: ...

class APIProvider(BaseProvider):
    # Existing Elia behavior - direct API calls
    def create_session(self) -> ChatSession: ...

class CLIProvider(BaseProvider):  
    # New behavior - tmux session management
    def create_session(self) -> TmuxSession: ...
    def discover_sessions(self) -> list[CLISessionInfo]: ...
```

#### Session Management Pattern
```python
# New session abstraction for CLI providers
class SessionManager:
    async def list_sessions(self, provider: CLIProvider) -> list[SessionInfo]:
        # Scan filesystem, parse session metadata
        
    async def attach_session(self, session_id: str) -> TmuxSession:
        # tmux attach-session -t session_id
        
    async def create_session(self, config: SessionConfig) -> TmuxSession:
        # tmux new-session -d -s session_id command
```

#### Widget Routing Pattern
```python
# Screen-level routing based on provider type
class HomeScreen(Screen[None]):
    async def action_send_message(self) -> None:
        selected_model = self.get_selected_model()
        
        if selected_model.provider_type == "api":
            # Existing Elia chat flow
            await self.app.launch_chat(prompt, selected_model)
        elif selected_model.provider_type == "cli":
            # New CLI session flow
            await self.app.launch_session(session_id, selected_model)
```

### Claude Code Integration Patterns

#### Session Discovery Pattern (IMPLEMENTED)
```python
class JSONLWatcher:
    """Discovers Claude Code sessions from JSONL files."""
    
    async def discover_sessions(self) -> list[ClaudeSession]:
        # Scan ~/.claude/projects/ for JSONL files
        projects_dir = Path.home() / ".claude/projects"
        sessions = []
        
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                for session_file in project_dir.glob("*.jsonl"):
                    try:
                        session = await self.parse_jsonl_session(session_file)
                        sessions.append(session)
                    except Exception as e:
                        logger.warning(f"Failed to parse session {session_file}: {e}")
        
        return sessions

    async def parse_jsonl_session(self, file_path: Path) -> ClaudeSession:
        """Parse JSONL file to extract session metadata."""
        # Parse first few lines for metadata, last lines for recent activity
        # Implement lazy loading to avoid reading entire large files
```

#### Claude Code CLI Integration Pattern (IMPLEMENTED) ✅
```python
class ClaudeCodeSession:
    """Direct Claude Code CLI integration with rich content extraction."""
    
    async def send_message(self, message: str, resume_session: bool = False) -> AsyncGenerator[ClaudeCodeResponse, None]:
        # Build Claude Code command with structured JSON output
        cmd = ["claude", "-p", "--verbose", "--output-format", "stream-json"]
        
        if resume_session and self.session_id:
            cmd.extend(["--resume", self.session_id])
        
        cmd.append(message)
        
        # Stream JSON responses directly from CLI
        async for response in self._read_streaming_json():
            yield response

    def _extract_message_content(self, message_obj: Dict[str, Any]) -> str:
        """Extract content using unified ContentExtractor for rich tool display."""
        # IMPLEMENTED: Uses ContentExtractor.extract_message_content() for consistency
        return ContentExtractor.extract_message_content(message_obj)
```

#### Streaming Message Grouping Pattern (NEW) ✅
```python
class StreamingMessageGrouper:
    """Groups streaming responses into coherent conversation blocks."""
    
    def add_response(self, response: ClaudeCodeResponse) -> Optional[GroupedMessage]:
        """Add streaming response and return complete grouped message if ready."""
        
        if response.message_type == "assistant":
            return self._handle_assistant_response(response)
        elif response.message_type == "user":
            return self._handle_user_response(response)  # Tool results
        elif response.message_type == "result":
            return self._handle_result_response(response)  # Completion
    
    def _finalize_current_group(self) -> Optional[GroupedMessage]:
        """Convert buffered responses into formatted GroupedMessage."""
        formatted_content = self._format_group_content()
        metadata = self._extract_group_metadata()
        
        return GroupedMessage(
            content=formatted_content,
            message_type="assistant", 
            metadata=metadata,
            is_complete=True
        )
```

#### Content Extraction Unification Pattern (NEW) ✅
```python
class ContentExtractor:
    """Unified content extraction for live and historical chat."""
    
    @staticmethod
    def extract_message_content(message_data: Dict[str, Any]) -> str:
        """Universal content extraction with tool support."""
        msg_type = message_data.get('type', '')
        
        if msg_type == "assistant":
            return ContentExtractor.extract_assistant_content(message_data)
        elif msg_type == "user":
            # Check for tool results first
            tool_results = ContentExtractor.extract_tool_result_content(message_data)
            return tool_results if tool_results else extract_user_content(message_data)
    
    @staticmethod  
    def extract_assistant_content(message_data: Dict[str, Any]) -> List[str]:
        """Extract reasoning + tool calls with rich formatting."""
        # Processes tool_use blocks: 🔧 **Used Read** (`toolu_01...`) Parameters: file_path: /test
        # Same logic as historical transformer for consistency
```

#### Session Intelligence Pattern
```python
class SessionMonitor:
    """Background monitoring for CLI sessions."""
    
    async def monitor_session(self, session_id: str) -> None:
        while session_active(session_id):
            # Capture session output
            output = await self.capture_session_output(session_id)
            
            # Generate intelligence summary
            summary = await self.generate_summary(output)
            
            # Update session status
            await self.update_session_status(session_id, summary)
            
            await asyncio.sleep(30)  # Monitor every 30 seconds
```

### Configuration Extension Patterns

#### CLI Provider Definitions
```python
# config.py - New builtin CLI providers
def get_builtin_cli_providers() -> list[EliaChatModel]:
    return [
        EliaChatModel(
            id="claude-code-session",
            name="Claude Code",
            display_name="Claude Code Session",
            provider="Claude Code",
            provider_type="cli",
            cli_command="claude code",
            session_manager="tmux",
            session_discovery=True,
            description="AI coding assistant with full codebase context"
        )
    ]

def get_builtin_models() -> list[EliaChatModel]:
    return (
        get_builtin_openai_models() +      # Existing
        get_builtin_anthropic_models() +   # Existing  
        get_builtin_google_models() +      # Existing
        get_builtin_cli_providers()        # New
    )
```

#### Session Configuration Pattern
```python
# TOML configuration for CLI providers
[providers.claude_code]
provider_type = "cli"
cli_command = "claude code"
session_manager = "tmux"
session_discovery = true
auto_resume = true

[providers.claude_code.session_config]
tmux_session_prefix = "cafedelia-"
max_concurrent_sessions = 5
session_timeout = 3600  # 1 hour
```

### Performance Optimization Patterns

#### Lazy Loading for Session Discovery
```python
class LazySessionLoader:
    """Implements pagination and lazy loading for large session datasets."""
    
    def __init__(self, page_size: int = 50):
        self.page_size = page_size
        self.cache = {}
    
    async def load_sessions_page(self, page: int = 0) -> list[SessionInfo]:
        """Load sessions in pages to avoid UI overload."""
        cache_key = f"sessions_page_{page}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        offset = page * self.page_size
        sessions = await self.discover_sessions_with_limit(offset, self.page_size)
        
        self.cache[cache_key] = sessions
        return sessions
    
    async def search_sessions(self, query: str) -> list[SessionInfo]:
        """Implement session filtering and search."""
        # TODO: Add search by project, date, content
        pass

class MessageParsingOptimizer:
    """Handles complex Claude Code message parsing."""
    
    def parse_tool_calls(self, message_content: dict) -> str:
        """Parse tool calls that were causing blank messages."""
        # TODO: Extract tool names and parameters
        # Handle <function_calls> blocks
        pass
    
    def parse_tool_results(self, result_data: dict) -> str:
        """Parse tool execution results."""
        # TODO: Format tool results for display
        pass
```

#### Database Extension Patterns (IMPLEMENTED) ✅
```sql
-- Enhanced chat table with proper session deduplication
-- FIXED: Added session_id field with unique constraint to prevent duplicates
ALTER TABLE chat ADD COLUMN session_id VARCHAR(255) NULL;
CREATE UNIQUE INDEX idx_chat_session_id ON chat(session_id) WHERE session_id IS NOT NULL;

-- Migration for cleanup and deduplication
-- Reduces 16k+ duplicate entries to clean dataset
DELETE FROM chat WHERE id NOT IN (
    SELECT MIN(id) FROM chat GROUP BY title  -- Keep earliest per title
);
DELETE FROM message WHERE chat_id NOT IN (SELECT id FROM chat);  -- Remove orphans
```

#### Deduplication Service Pattern (NEW) ✅
```python
class DeduplicationService:
    """Thread-safe session synchronization preventing race conditions."""
    
    @asynccontextmanager
    async def sync_session(self, session_id: str, session_timestamp: float):
        """Context manager for safe session synchronization."""
        should_sync = await self.should_sync_session(session_id, session_timestamp)
        
        if not should_sync:
            yield False
            return
        
        async with self.sync_lock.acquire_session_lock(session_id):
            await self.mark_sync_start(session_id)
            try:
                yield True
                await self.mark_sync_complete(session_id, session_timestamp, success=True)
            except Exception as e:
                await self.mark_sync_complete(session_id, session_timestamp, success=False)
                raise

# Usage in JSONLTransformer
async def sync_session_to_database(self, session: ClaudeSession, messages: List[dict]):
    async with deduplication_service.sync_session(session.session_id, session.last_updated) as should_sync:
        if should_sync:
            # Perform actual sync with guaranteed uniqueness
            pass
```

### Integration Points Summary

#### Extension Points (Modify Existing)
- **EliaChatModel**: Add CLI provider fields
- **OptionsModal**: Add provider type selection UI
- **HomeScreen**: Add CLI provider routing logic
- **LaunchConfig**: Include CLI providers in model lists

#### New Components (Add to Existing)
- **TmuxSessionWidget**: CLI session display
- **SessionScreen**: CLI provider interface screen
- **CLIProvider**: Base class for CLI tool integration
- **SessionManager**: CLI session lifecycle management
- **SessionMonitor**: Background intelligence generation

#### Preserved Components (Keep Unchanged)
- **API Provider Flow**: All existing chat functionality
- **Database Core**: Existing chat persistence patterns
- **Theme System**: Visual customization capabilities
- **Screen Management**: Navigation and modal patterns

This architecture preserves Elia's strengths while adding the CLI provider capabilities needed to transform it into a comprehensive AI session management platform.
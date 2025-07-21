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

#### Session Discovery Pattern
```python
class ClaudeCodeProvider(CLIProvider):
    async def discover_sessions(self) -> list[ClaudeCodeSession]:
        # Scan ~/.config/claude-code/sessions/
        session_dir = Path.home() / ".config/claude-code/sessions"
        sessions = []
        
        for session_file in session_dir.glob("*.json"):
            metadata = self.parse_session_metadata(session_file)
            sessions.append(ClaudeCodeSession(
                id=metadata.id,
                project=metadata.project,
                last_activity=metadata.last_activity,
                git_branch=metadata.git_branch
            ))
        
        return sessions
```

#### Tmux Integration Pattern
```python
class TmuxSessionWidget(Widget):
    """Embeds tmux session within Textual interface."""
    
    def __init__(self, session_name: str, command: str):
        self.session_name = session_name
        self.command = command
    
    async def on_mount(self) -> None:
        if await self.session_exists():
            await self.attach_session()
        else:
            await self.create_session()
            
    async def create_session(self) -> None:
        # tmux new-session -d -s {session_name} {command}
        await asyncio.create_subprocess_exec(
            "tmux", "new-session", "-d", "-s", self.session_name, self.command
        )
        
    async def attach_session(self) -> None:
        # Embed tmux session in current terminal area
        # Use tmux's terminal control features
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

### Database Extension Patterns

#### Session Tracking Schema
```sql
-- Extend Elia's existing database with CLI session tracking
CREATE TABLE cli_sessions (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    session_name TEXT NOT NULL,
    project_path TEXT,
    git_branch TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP,
    intelligence_summary TEXT
);

CREATE TABLE session_intelligence (
    session_id TEXT REFERENCES cli_sessions(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    summary_type TEXT,  -- 'progress', 'error', 'completion'
    summary_content TEXT,
    confidence_score REAL
);
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
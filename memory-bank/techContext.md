# Technical Context

## Development Environment

### Project Structure
```
/home/alex/code/cafedelia/           # Elia fork for CLI provider integration
├── elia_chat/                      # Main source code (inherited from Elia)
│   ├── app.py                      # Main Textual application
│   ├── config.py                   # Model/provider configuration (KEY EXTENSION POINT)
│   ├── screens/                    # Screen management
│   │   ├── home_screen.py          # Model selection + session browser
│   │   ├── chat_screen.py          # API provider interface
│   │   └── [NEW] session_screen.py # CLI provider interface
│   ├── widgets/                    # UI components
│   │   ├── chat_options.py         # Provider selection (KEY EXTENSION POINT)
│   │   ├── chat.py                 # API provider display
│   │   └── [NEW] tmux_session.py   # CLI provider display
│   └── database/                   # SQLite persistence
├── memory-bank/                    # Project documentation
├── pyproject.toml                  # Python project configuration
└── README.md                       # Project documentation
```

### Technology Stack

#### Core Framework (Inherited from Elia)
- **Textual**: Python terminal UI framework
  - Version: Latest stable (0.80+)
  - Reactive, modern TUI with CSS-like styling
  - Web deployment capability for future expansion
  - Screen-based navigation and modal system

#### Language and Runtime
- **Python 3.11+**: Required for modern async/await patterns
- **Type Hints**: Full typing for maintainability
- **Pydantic**: Configuration and data validation
- **Rich**: Text rendering and markup (Textual dependency)

#### Data and Persistence
- **SQLite**: Database for chat history and session tracking
  - Existing Elia schema for chat persistence
  - Extension planned for CLI session intelligence
- **TOML**: Configuration file format (inherited from Elia)
- **JSON**: Session metadata and intelligence summaries

#### External Integrations
- **tmux**: Terminal multiplexer for session management
  - Required for CLI provider functionality
  - Session creation, attachment, persistence
- **Claude Code**: Primary CLI provider integration
  - Session discovery from ~/.config/claude-code/sessions/
  - --resume functionality for session attachment
- **Git**: Repository and worktree management
  - Session context from git branch information
  - Future: automated worktree coordination

### Dependencies

#### Core Dependencies (Inherited)
```toml
[dependencies]
textual = ">=0.80.0"           # Terminal UI framework
pydantic = ">=2.0.0"           # Configuration validation
rich = ">=13.0.0"              # Text rendering (Textual dependency)
litellm = ">=1.0.0"            # LLM API abstraction (for API providers)
```

#### Implemented Dependencies (CLI Provider Support)
```toml
# Current dependencies for Claude Code CLI integration
aiofiles = ">=24.1.0"          # Async file operations for JSONL parsing
psutil = ">=5.9.0"             # Process monitoring for CLI sessions
# Note: libtmux removed - using direct CLI integration instead
```

#### Development Dependencies
```toml
[dev-dependencies]
pytest = ">=7.0.0"             # Testing framework
black = ">=23.0.0"             # Code formatting
ruff = ">=0.1.0"               # Linting and static analysis
mypy = ">=1.0.0"               # Type checking
```

### Configuration System

#### Model Configuration (Extended from Elia)
```python
# config.py - EliaChatModel extensions
class EliaChatModel(BaseModel):
    # Existing Elia fields...
    name: str
    provider: str | None = None
    api_key: SecretStr | None = None
    
    # New CLI provider fields
    provider_type: Literal["api", "cli"] = "api"
    cli_command: str | None = None       # e.g. "claude code"
    session_manager: str | None = None    # e.g. "tmux"
    session_discovery: bool = False       # Auto-detect existing sessions
```

#### TOML Configuration Extensions
```toml
# ~/.config/cafedelia/config.toml
[general]
default_model = "claude-code-session"
theme = "nebula"

# Existing API providers (preserved)
[[models]]
id = "elia-claude-3-5-sonnet"
name = "claude-3-5-sonnet-20240620"
provider_type = "api"
provider = "Anthropic"

# New CLI providers
[[models]]
id = "claude-code-session"
name = "Claude Code"
provider_type = "cli"
provider = "Claude Code"
cli_command = "claude code"
session_manager = "tmux"
session_discovery = true

[cli_providers.claude_code]
session_prefix = "cafedelia-"
max_concurrent_sessions = 5
auto_resume = true
```

### Development Setup

#### Installation and Environment
```bash
# Clone cafedelia repository
git clone /path/to/cafedelia
cd cafedelia

# Create virtual environment (Python 3.11+)
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Install globally with pipx (recommended)
pipx uninstall cafedelia  # Remove previous version
pipx install -e .         # Install from development directory

# Database location
~/.local/share/cafedelia/cafedelia.sqlite  # Correct database path
```

#### Development Prerequisites
```bash
# Required external tools
sudo apt install tmux              # Session management
pip install claude-code           # CLI provider to integrate

# Optional but recommended
sudo apt install git              # Repository management
pip install pre-commit           # Git hooks for code quality
```

#### Running Cafedelia
```bash
# Development mode (current)
python -m elia_chat

# Production installation (planned)
cafedelia

# With Claude Code integration (implemented)
python -m elia_chat  # Auto-detects Claude Code sessions

# Performance debugging
python -m elia_chat --debug  # For investigating parsing issues
```

### Development Patterns

#### Async/Await for CLI Integration
```python
# All CLI provider operations use async patterns
class SessionManager:
    async def create_session(self, config: SessionConfig) -> TmuxSession:
        # Non-blocking session creation
        proc = await asyncio.create_subprocess_exec(
            "tmux", "new-session", "-d", "-s", config.name, config.command
        )
        await proc.wait()
        
    async def discover_sessions(self) -> list[SessionInfo]:
        # Non-blocking filesystem scanning
        async with aiofiles.open(session_file) as f:
            content = await f.read()
```

#### Type Safety and Validation
```python
# All configuration uses Pydantic models
class SessionConfig(BaseModel):
    session_id: str
    provider: str
    command: str
    project_path: Path | None = None
    
class SessionInfo(BaseModel):
    id: str
    status: Literal["active", "inactive", "error"]
    last_activity: datetime
    project: str | None = None
```

#### Error Handling Patterns
```python
# Graceful degradation for CLI provider failures
async def attach_session(self, session_id: str) -> TmuxSession | None:
    try:
        session = await self.tmux_manager.attach(session_id)
        return session
    except SessionNotFoundError:
        self.log.warning(f"Session {session_id} not found")
        return None
    except TmuxError as e:
        self.log.error(f"Tmux error: {e}")
        # Fall back to API provider or show error screen
        return None
```

### Build and Deployment

#### Package Configuration
```toml
# pyproject.toml (inherited and extended)
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "cafedelia"
description = "Terminal AI session management with CLI provider support"
dependencies = [
    "textual>=0.80.0",
    "pydantic>=2.0.0", 
    "libtmux>=0.30.0",
    "aiofiles>=24.1.0",
]

[project.scripts]
cafedelia = "elia_chat.__main__:main"

[project.optional-dependencies]
dev = ["pytest", "black", "ruff", "mypy"]
```

#### Testing Strategy
```python
# Test structure for CLI provider functionality
tests/
├── unit/
│   ├── test_session_discovery.py    # Session scanning logic
│   ├── test_tmux_integration.py     # Tmux session management
│   └── test_provider_routing.py     # API vs CLI provider routing
├── integration/
│   ├── test_claude_code_provider.py # End-to-end Claude Code integration
│   └── test_session_lifecycle.py    # Session creation/attachment/cleanup
└── fixtures/
    ├── mock_sessions/               # Test session data
    └── mock_tmux/                   # Tmux simulation
```

### Performance Considerations

#### Database Deduplication (FIXED) ✅
**Previous Issue**: 15k duplicate database entries causing massive bloat
- **Root Cause**: Broken `title.contains()` session matching with race conditions
- **Solution Implemented**: 
  - Added `session_id` field with unique constraint
  - Centralized deduplication service with sync locking
  - Database migration and cleanup (16,083 → 184 chats)
- **Result**: Clean, efficient database with proper deduplication

#### Message Parsing Efficiency (IMPROVED) ✅ 
**Previous Issue**: Blank agent messages from failed tool parsing
- **Solution Implemented**: 
  - Unified `ContentExtractor` class for consistent parsing
  - Rich tool call extraction with parameters and formatting
  - Streaming message grouper for coherent conversation display
- **Current Issue**: Tool results still not displaying in live chat despite fixes

#### Session Discovery Optimization (STABLE)
**Current Status**: JSONL file parsing and SQLite sync working well
- **Implemented**: Efficient session discovery from `~/.claude/projects/`
- **Performance**: Handles ~2000 sessions effectively with database caching
- **Future Need**: Pagination/lazy loading for UI optimization when session count grows

#### Memory Management
- **Current**: Direct CLI process management without tmux
- **Needed**: Limit concurrent CLI sessions to prevent resource exhaustion
- **Needed**: Stream processing optimization for large responses
- **Needed**: Database query optimization for session metadata

### Security Considerations

#### Session Isolation
- Each CLI session runs in isolated tmux session
- No cross-session file system access
- Proper cleanup of temporary files and sessions

#### Configuration Security
- API keys stored using Pydantic SecretStr
- CLI command validation to prevent injection
- Sandboxed session execution where possible

### Future Technical Considerations

#### Scalability
- Plugin architecture for additional CLI providers
- Configurable resource limits per provider
- Horizontal scaling for team collaboration features

#### Integration Expansion
- VS Code extension for desktop integration
- Web interface using Textual's web deployment
- API for external tool integration

This technical foundation builds on Elia's proven architecture while adding the CLI provider capabilities needed for comprehensive AI session management.
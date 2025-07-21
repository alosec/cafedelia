# Cafedelia

**The Terminal GUI for Claude Code Session Management**

Cafedelia provides the visual interface and session intelligence that Claude Code should have had from the beginning. Built on Elia's proven Textual framework, Cafedelia transforms Claude Code from a powerful but primitive CLI tool into a comprehensive terminal GUI.

![Cafedelia - Claude Code Session Management](https://via.placeholder.com/800x400/2D2D2D/FFFFFF?text=Cafedelia%3A+Claude+Code+GUI)

## Why Cafedelia?

**Claude Code is incredibly powerful but has interface limitations:**
- Manual session management with `claude code --resume <session-id>`
- No way to see what sessions exist or their status  
- No visual model selection or configuration
- Sessions are "black boxes" with no progress visibility

**Cafedelia solves these problems:**
- **Visual Session Browser**: See all Claude Code sessions at a glance
- **Model Configuration GUI**: Easy selection of Claude 3.5 Sonnet, Haiku, Opus
- **Session Intelligence**: Progress tracking and achievement summaries  
- **Terminal-Native**: Built for developers who live in the terminal

## Features

- **🔍 Session Discovery**: Automatically find all Claude Code sessions from `~/.claude/__store.db`
- **📊 Session Browser**: Visual interface for browsing and organizing sessions by project
- **🎯 Model Selection**: GUI for choosing between Claude Code's available models
- **📈 Session Intelligence**: Progress tracking and session achievement summaries
- **🖥️ Terminal Integration**: Embedded tmux sessions within beautiful Textual interface
- **⚡ Quick Access**: One-click session attachment without memorizing session IDs
- **🗂️ Project Organization**: Group sessions by project and git branch
- **🎨 Beautiful UI**: Professional terminal interface built on Textual framework

## Installation

### Prerequisites

- **Claude Code**: Cafedelia is a GUI wrapper for Claude Code
- **tmux**: Required for session management (usually pre-installed)

```bash
# Install Claude Code (if not already installed)
npm install -g @anthropic-ai/claude-code

# Install tmux (if not already installed)
# Ubuntu/Debian:
sudo apt install tmux
# macOS:
brew install tmux
```

### Install Cafedelia

**Using `pipx` (recommended):**

```bash
pipx install cafedelia
```

**Using `pip`:**

```bash
pip install cafedelia
```

After installation, run Cafedelia using the `cafedelia` command.

## Getting Started

1. **Install Claude Code and Cafedelia** using the instructions above
2. **Set your Anthropic API key** (required for Claude Code):
   ```bash
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```
3. **Run Cafedelia**:
   ```bash
   cafedelia
   ```
4. **Browse your Claude Code sessions** visually in the interface
5. **Select or create sessions** with one-click access

### First Time Setup

When you first run Cafedelia:
- It will create its own database at `~/.local/share/cafedelia/cafedelia.sqlite`
- Existing Claude Code sessions will be automatically discovered from `~/.claude/__store.db`
- You can immediately browse and attach to any existing Claude Code sessions

### Claude Code Integration

Cafedelia works by:
- **Session Discovery**: Reading Claude Code's session data from `~/.claude/__store.db`
- **Tmux Integration**: Launching Claude Code sessions in tmux for terminal embedding
- **Intelligent Display**: Showing session metadata, project context, and progress

## Configuration

Cafedelia can be configured using a TOML file located at `~/.config/cafedelia/config.toml`.

Here's an example configuration file:

```toml
[general]
# The default Claude model to use for new sessions
default_model = "claude-3-5-sonnet-20241022"

# UI theme - choose from "dark", "light", "nebula", "sunset", "nord", "dracula", "synthwave"
theme = "dark"

[claude_code]
# Claude Code session discovery settings
auto_discover_sessions = true
session_refresh_interval = 30  # seconds

# Model preferences for Claude Code
available_models = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022", 
    "claude-3-opus-20240229"
]

# Session management
max_concurrent_sessions = 5
session_timeout = 3600  # 1 hour
```

## Usage

### Basic Usage

Run Cafedelia to open the Claude Code session browser:

```bash
cafedelia
```

### Session Management

- **Browse Sessions**: See all Claude Code sessions with project context and timestamps
- **Attach to Session**: Click any session to attach to it via tmux integration
- **Create New Session**: Start a new Claude Code session with selected model and project
- **Monitor Progress**: View session intelligence and achievement summaries

### Key Bindings

- `ctrl+o` - Open model configuration and session options
- `ctrl+n` - Create a new Claude Code session
- `ctrl+s` - Save current session state
- `ctrl+r` - Refresh session list from Claude Code database
- `ctrl+x` - Exit Cafedelia
- `escape` - Go back or close modal
- `f1` or `?` - Open help
- `tab` and `shift+tab` - Navigate between UI elements

### Integration with Claude Code

Cafedelia seamlessly integrates with your existing Claude Code workflow:
- All existing sessions are automatically discovered
- Session attachments preserve tmux environment
- Model configurations sync with Claude Code settings
- No changes to your existing Claude Code workflow required

## Architecture

Cafedelia is built on proven technologies:

- **[Textual Framework](https://github.com/Textualize/textual)**: Modern Python terminal UI framework
- **Claude Code Integration**: Direct integration with Claude Code's session system
- **tmux**: Terminal multiplexer for session management
- **SQLite**: Local database for session intelligence and caching

## Development Status

> **Status**: Early Development - Core functionality being implemented

### Current Status
- ✅ Standalone Cafedelia application
- ✅ Complete branding and identity  
- ✅ Database separation from Elia
- 🚧 Claude Code session discovery
- 🚧 Model configuration GUI
- 📋 Session intelligence and monitoring

## Relationship to Elia

Cafedelia is a focused fork of [Elia](https://github.com/darrenburns/elia) specifically designed for Claude Code session management. While Elia is a general-purpose LLM chat interface, Cafedelia is purpose-built to be the GUI that Claude Code should have had from the beginning.

## Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

Areas of focus:
- Claude Code integration and session management
- Textual UI development for terminal environments
- Session intelligence and progress tracking
- Terminal workflow optimization

## License

MIT

## Acknowledgements

- Built on the [Textual framework](https://github.com/Textualize/textual) by [Textualize](https://www.textualize.io/)
- Forked from [Elia](https://github.com/darrenburns/elia) by [Darren Burns](https://github.com/darrenburns)
- Designed specifically for [Claude Code](https://claude.ai/code) by Anthropic
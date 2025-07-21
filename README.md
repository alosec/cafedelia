<h1 align="center">
    Cafedelia
</h1>
<p align="center">
  <i align="center">Terminal AI session management platform - Beautiful UI meets serious workflow orchestration</i><br>
  <i align="center">Fork of Elia with Claude Code CLI provider integration for professional AI-assisted development</i>
</p>

![elia-screenshot-collage](https://github.com/darrenburns/elia/assets/5740731/75f8563f-ce1a-4c9c-98c0-1bd1f7010814)

## Introduction

**Cafedelia** transforms Elia from a beautiful terminal chat wrapper into a comprehensive AI session management platform. Built for terminal developers who want the polish of Elia's Textual UI combined with the power of Claude Code's workflow capabilities.

### The Vision

Existing terminal LLM tools fall into limited categories:
- **Chat Wrappers** (Elia, basic clients): Beautiful interfaces but no workflow capabilities  
- **Workflow Tools** (Claude Code, Aider): Powerful agents but primitive session management

**Cafedelia bridges this gap** - terminal-native session management with serious workflow orchestration.

### Key Features

- **CLI Provider Support**: Beyond API providers, integrate tools like Claude Code as first-class citizens
- **Session Discovery**: Find and manage existing Claude Code sessions from the filesystem
- **Tmux Integration**: Embed terminal sessions within the beautiful Textual interface
- **Session Intelligence**: Background monitoring and workflow coordination
- **Terminal-Native**: No context switching to desktop applications

Built on Elia's proven foundation: SQLite persistence, robust configuration, professional UI patterns, and theme system.

## Installation

> **Status**: In Development - Cafedelia is currently being built as an Elia fork with CLI provider support.

**Current Phase**: Implementing provider type separation and Claude Code integration.

### Prerequisites

- Python 3.11+
- Claude Code CLI (`pip install claude-cli`)
- tmux (for session management)

### Development Installation

```bash
git clone https://github.com/alosec/cafedelia.git
cd cafedelia
pip install -e .
```

### Environment Setup

For API providers, set environment variables:
- `OPENAI_API_KEY` - For ChatGPT models
- `ANTHROPIC_API_KEY` - For Claude models  
- `GEMINI_API_KEY` - For Google models

For Claude Code integration:
- Ensure `claude code` command is available
- Existing Claude Code sessions will be auto-discovered

## Usage

### API Providers (Inherited from Elia)

Launch with traditional chat interface:
```bash
cafedelia -m gpt-4o "Help me debug this function"
```

### CLI Providers (Cafedelia Innovation)

**Session Discovery**: Browse existing Claude Code sessions
```bash
cafedelia --provider claude-code --list-sessions
```

**Session Management**: Launch or resume sessions in terminal UI
```bash
cafedelia --provider claude-code --session my-project
```

**Background Intelligence**: Monitor active sessions
```bash
cafedelia --monitor --session-intelligence
```

## Running local models

1. Install [`ollama`](https://github.com/ollama/ollama).
2. Pull the model you require, e.g. `ollama pull llama3`.
3. Run the local ollama server: `ollama serve`.
4. Add the model to the config file (see below).

## Configuration

Cafedelia extends Elia's configuration system with CLI provider support. Configuration location shown in options window (`ctrl+o`).

### Basic Configuration

```toml
# Default provider selection
default_provider_type = "cli"  # "api" or "cli"
default_model = "claude-code-session"

# UI preferences  
theme = "galaxy"
message_code_theme = "dracula"
```

### API Providers (Inherited from Elia)

```toml
[[models]]
name = "gpt-4o"
provider_type = "api"  # explicit for clarity

[[models]]
name = "ollama/llama3"
provider_type = "api"

[[models]]
name = "groq/llama2-70b-4096"
display_name = "Llama 2 70B"
provider = "Groq"
provider_type = "api"
```

### CLI Providers (Cafedelia Innovation)

```toml
# Claude Code integration
[[models]]
id = "claude-code-session"
name = "Claude Code"
display_name = "Claude Code Session"
provider_type = "cli"
cli_command = "claude code"
session_manager = "tmux"

# Future CLI providers
[[models]]
id = "aider-session"  
name = "Aider"
display_name = "Aider Coding Assistant"
provider_type = "cli"
cli_command = "aider"
session_manager = "tmux"
```

### Session Management

```toml
[session_management]
# Session discovery settings
auto_discover = true
session_timeout = "1h"
background_monitoring = true

# Tmux integration
tmux_session_prefix = "cafedelia"
tmux_control_mode = true
```

## Custom themes

Add a custom theme YAML file to the themes directory.
You can find the themes directory location by pressing `ctrl+o` on the home screen and looking for the `Themes directory` line.

Here's an example of a theme YAML file:

```yaml
name: example  # use this name in your config file
primary: '#4e78c4'
secondary: '#f39c12'
accent: '#e74c3c'
background: '#0e1726'
surface: '#17202a'
error: '#e74c3c'  # error messages
success: '#2ecc71'  # success messages
warning: '#f1c40f'  # warning messages
```

## Changing keybindings

Right now, keybinds cannot be changed. Terminals are also rather limited in what keybinds they support.
For example, pressing <kbd>Cmd</kbd>+<kbd>Enter</kbd> to send a message is not possible (although we may support a protocol to allow this in some terminals in the future).

For now, I recommend you map whatever key combo you want at the terminal emulator level to send `\n`.
Here's an example using iTerm:

<img width="848" alt="image" src="https://github.com/darrenburns/elia/assets/5740731/94b6e50c-429a-4d17-99c2-affaa828f35b">

With this mapping in place, pressing <kbd>Cmd</kbd>+<kbd>Enter</kbd> will send a message to the LLM, and pressing <kbd>Enter</kbd> alone will create a new line.

## Development Status

Cafedelia is actively being developed as an Elia fork. Current implementation phases:

### ✅ Completed
- [x] **Project Foundation**: Memory bank, architecture documentation
- [x] **Repository Setup**: Clean fork with independent git history  
- [x] **Vision Definition**: Clear product strategy and technical approach

### 🚧 In Progress  
- [ ] **Provider Type Separation**: Extend OptionsModal for API vs CLI selection
- [ ] **Claude Code Integration**: Session discovery and management
- [ ] **Tmux Embedding**: Terminal session display within Textual interface

### 📋 Planned
- [ ] **Session Intelligence**: Background monitoring and summarization
- [ ] **Cross-Session Coordination**: Workflow orchestration capabilities
- [ ] **Additional CLI Providers**: Aider, other AI development tools

## Contributing

Cafedelia represents the missing link between beautiful terminal interfaces and serious AI workflow management. We're building the session intelligence layer that should have existed from the beginning.

**Areas of Focus**:
- Textual UI development and tmux integration
- AI workflow orchestration patterns
- Terminal-native session management
- Claude Code and AI tool integrations

## Project Goals

Transform terminal AI interaction from simple chat to comprehensive session management:

1. **Preserve Elia's Strengths**: Beautiful UI, robust configuration, professional patterns
2. **Add CLI Provider Support**: First-class integration with tools like Claude Code  
3. **Enable Session Intelligence**: Background monitoring and workflow coordination
4. **Stay Terminal-Native**: No desktop context switching required

## Acknowledgments

Built upon [Elia](https://github.com/darrenburns/elia) by Darren Burns - an excellent foundation for terminal LLM interaction that deserved serious workflow capabilities.

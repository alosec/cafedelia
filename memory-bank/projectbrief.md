# Cafedelia Project Brief

## Project Name
Cafedelia - Elia Fork with Claude Code CLI Provider Integration

## Vision
Transform Elia from a beautiful terminal chat wrapper into a comprehensive AI session management platform by adding CLI provider support, with Claude Code as the flagship integration. Cafedelia bridges the gap between polished terminal UIs and serious AI workflow orchestration.

## Core Problem
Existing terminal LLM tools fall into two limited categories:
1. **Chat Wrappers** (Elia, basic terminal clients): Beautiful interfaces but no workflow capabilities
2. **Workflow Tools** (Claude Code, Aider): Powerful agents but primitive session management

**Missing**: A terminal-native platform that combines beautiful UI with serious session management and workflow orchestration.

## Solution Architecture
**Fork Elia + Add CLI Provider Support + Claude Code Integration**

### Phase 1: Provider Type Separation
Extend Elia's provider system to distinguish:
- **API Providers**: Existing OpenAI, Anthropic, Google (chat-based)
- **CLI Providers**: New category for tools like Claude Code (session-based)

### Phase 2: Claude Code Integration
Replace chat interface with tmux session management:
- **Session Discovery**: Find existing `claude code --resume` sessions
- **Session Creation**: Launch new Claude Code instances in tmux
- **Session Embedding**: Display tmux sessions within Textual interface
- **Session Intelligence**: Background monitoring with `claude -p` summaries

### Phase 3: Workflow Enhancement
Add session orchestration capabilities:
- Cross-session task delegation
- Background session monitoring
- Git worktree integration
- Project-level session coordination

## Key Differentiators

### vs Pure Elia
- **Workflow Management**: Real AI session orchestration vs simple chat
- **CLI Tool Integration**: Bridge to powerful development tools
- **Session Persistence**: Background session management vs ephemeral conversations

### vs Desktop Tools (Crystal, Conductor)
- **Terminal-Native**: No context switching from developer environment
- **Textual Framework**: Rich terminal UI capabilities (web deployment, reactive updates)
- **Professional Integration**: tmux compatibility, existing workflow preservation

### vs Other Terminal LLM Tools
- **Framework Choice**: Textual vs ubiquitous Rust/Ratatui alternatives
- **Session Focus**: Intelligence layer for workflow management vs simple chat interfaces
- **Integration Depth**: Native Claude Code filesystem integration

## Success Metrics
1. **Session Management**: Successfully launch, attach, and manage Claude Code sessions
2. **UI Integration**: Seamless tmux embedding within Textual interface
3. **Workflow Enhancement**: Background session monitoring and intelligence
4. **Developer Adoption**: Terminal-native alternative to desktop session managers

## Technical Foundation
**Leverage Elia's Strengths**:
- Proven Textual UI framework
- Robust configuration system (TOML, models, themes)
- SQLite persistence for chat history
- Professional screen management and navigation

**Add Cafedelic Intelligence**:
- CLI provider architecture
- Tmux session integration
- Claude Code session discovery
- Background monitoring and summarization

## Target Audience
Developers who want:
- Beautiful terminal interfaces (Elia's strength)
- Serious AI workflow management (Claude Code's strength)
- Session intelligence and coordination (Cafedelic's innovation)
- Terminal-native operation (no desktop app context switching)

## Project Scope
**In Scope**:
- Elia fork with CLI provider support
- Claude Code integration as first CLI provider
- Tmux session management within Textual interface
- Session discovery and background monitoring

**Future Scope**:
- Additional CLI providers (Aider, other AI tools)
- Advanced workflow orchestration
- Cross-session task delegation
- Git worktree automation

**Out of Scope**:
- New LLM API integrations (use Elia's existing)
- Desktop application development
- Non-terminal UI frameworks
- Claude Code replacement or modification

## Implementation Strategy
1. **Incremental Enhancement**: Start with working Elia, add features step-by-step
2. **Provider Pattern**: Extend existing model/provider system rather than replace
3. **Textual Best Practices**: Follow established screen/widget patterns
4. **Session Intelligence**: Focus on workflow orchestration as key differentiator

Cafedelia represents the missing link between beautiful terminal interfaces and serious AI workflow management - the session intelligence layer that should have existed from the beginning.
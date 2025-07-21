# Cafedelia Project Brief

## Project Name
Cafedelia - The Terminal GUI for Claude Code

## Vision
Transform Elia's beautiful Textual interface into a comprehensive GUI wrapper for Claude Code session management. Cafedelia provides the visual interface and session intelligence that Claude Code should have had from the beginning.

## Core Problem
Claude Code is incredibly powerful but lacks proper session management:
1. **No Session Visibility**: Can't see what sessions exist or their status
2. **Primitive CLI Interface**: Manual session ID management with `--resume` 
3. **No Session Intelligence**: Sessions are "black boxes" with no progress visibility
4. **Poor Session Organization**: No project-based grouping or context awareness

**Missing**: A terminal-native GUI that makes Claude Code sessions visual, organized, and intelligent.

## Solution Architecture
**Fork Elia + Focus Entirely on Claude Code Session Management**

### Phase 1: Claude Code Session Discovery
Replace Elia's chat interface with Claude Code session management:
- **Session Browser**: Visual list of all Claude Code sessions from filesystem
- **Session Metadata**: Project context, last activity, git branch information
- **Session Status**: Active/inactive detection and health monitoring

### Phase 2: Session Interface Integration
Embed Claude Code sessions within Textual interface:
- **Tmux Integration**: Display Claude Code sessions in terminal widgets
- **Session Creation**: Launch new Claude Code instances with project context
- **Session Attachment**: One-click access to existing sessions

### Phase 3: Session Intelligence
Add intelligence layer for session management:
- **Session Summaries**: Monitor session progress and achievements
- **Project Organization**: Group sessions by project and branch
- **Model Configuration**: GUI for Claude Code's available models

## Key Differentiators

### vs Pure Claude Code CLI
- **Visual Interface**: See all sessions at a glance vs manual `--resume` commands
- **Session Intelligence**: Progress monitoring and summaries vs black box sessions
- **Project Organization**: Grouped sessions by project vs scattered session IDs

### vs Desktop Tools (Crystal, Conductor)
- **Terminal-Native**: No context switching from developer environment
- **Lightweight**: Direct Claude Code integration vs complex Electron wrappers
- **Professional Integration**: tmux compatibility, existing workflow preservation

### vs Other Terminal LLM Tools
- **Claude Code Focus**: Purpose-built for the most powerful coding assistant
- **Textual Framework**: Rich terminal UI vs basic CLI interfaces
- **Session-Centric**: Built around persistent coding sessions vs ephemeral conversations

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
- Generic CLI provider framework
- Other AI tool integrations (Aider, etc.)
- Desktop application development
- Claude Code replacement or modification

## Implementation Strategy
1. **Incremental Enhancement**: Start with working Elia, add features step-by-step
2. **Provider Pattern**: Extend existing model/provider system rather than replace
3. **Textual Best Practices**: Follow established screen/widget patterns
4. **Session Intelligence**: Focus on workflow orchestration as key differentiator

Cafedelia represents the missing link between beautiful terminal interfaces and serious AI workflow management - the session intelligence layer that should have existed from the beginning.
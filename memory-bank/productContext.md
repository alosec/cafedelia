# Product Context

## Why Cafedelia Exists

### The Terminal LLM Tool Limitation
Existing terminal-based LLM tools fall into two limiting categories:

**Chat Wrappers** (Beautiful but Limited):
- Elia: Gorgeous Textual UI, but just API chat
- Basic terminal clients: Simple conversation interfaces
- **Problem**: No workflow capabilities, no session management, no persistent context

**Workflow Tools** (Powerful but Primitive):
- Claude Code: Sophisticated agent with codebase awareness
- Aider: Git integration and multi-file coordination
- **Problem**: Minimal session management (just `--resume`), no intelligence layer

### The Gap Cafedelia Fills
**Missing**: A terminal-native platform that combines beautiful UI with serious AI workflow orchestration.

Cafedelia bridges this gap by taking Elia's proven Textual interface and adding the session management layer that tools like Claude Code should have had from the beginning.

## Problems Cafedelia Solves

### 1. **Session Discovery and Management**
**Current State**: Claude Code sessions are opaque
- No way to see what sessions exist
- No organization or categorization
- Manual session ID management with `--resume`

**Cafedelia Solution**: Visual session browser with intelligent discovery
- List all existing Claude Code sessions
- Show session metadata (project, last activity, git branch)
- One-click session attachment or creation

### 2. **Context Switching Overhead**
**Current State**: Constant environment switching
- Switch between terminal and desktop session managers (Crystal, Conductor)
- Leave terminal environment to manage AI workflows
- Break developer flow with context switching

**Cafedelia Solution**: Terminal-native session management
- Stay in terminal environment throughout workflow
- Tmux integration preserves existing setup
- Professional screen management with Textual interface

### 3. **Session Intelligence Gap**
**Current State**: Sessions are "black boxes"
- No visibility into background session progress
- No cross-session coordination
- No understanding of session relationships

**Cafedelia Solution**: Intelligence layer with `claude -p` integration
- Background session monitoring and summarization
- Cross-session pattern recognition
- Task delegation with session-aware routing

### 4. **Workflow Orchestration Limitation**
**Current State**: Manual session coordination
- No automated handoffs between sessions
- No project-level session organization
- No git worktree integration for parallel development

**Cafedelia Solution**: Orchestrated workflow management
- Project-based session grouping
- Git worktree integration for parallel contexts
- Background task delegation and coordination

## User Experience Goals

### Primary User Journey
```
Developer Working on Feature:
1. Open Cafedelia (instead of basic claude code)
2. Browse existing sessions by project/context  
3. Select relevant session or create new one
4. Work in embedded tmux Claude Code session
5. Monitor background sessions with intelligence summaries
6. Delegate related tasks to appropriate sessions
7. Switch between sessions without losing context
```

### Key Experience Principles

**Stay in Terminal**: Never force context switching to desktop apps
**Preserve Workflow**: Work with existing tmux/terminal setup, don't replace it  
**Add Intelligence**: Layer session insights on top of existing Claude Code power
**Visual Polish**: Maintain Elia's beautiful Textual interface standards

## Target Audience

### Primary: Terminal-Native Developers
- Live in terminal environment
- Use tmux or similar multiplexers
- Want AI assistance without workflow disruption
- Value both aesthetics and functionality

### Secondary: AI-Assisted Development Teams
- Work with multiple Claude Code sessions
- Need session coordination and handoffs
- Want background monitoring of AI progress
- Require project-level organization

### Personas

**"Terminal Power User"**:
- Spends 8+ hours in terminal daily
- Has sophisticated tmux configurations  
- Wants AI tools to integrate seamlessly
- Values keyboard-driven interfaces

**"AI Workflow Manager"**:
- Runs multiple parallel AI sessions
- Needs session intelligence and coordination
- Wants background monitoring capabilities
- Requires project-level organization

## Competitive Positioning

### vs Pure Elia
**Elia**: Beautiful chat interface, limited to API conversations
**Cafedelia**: Same beautiful interface + serious workflow management + CLI tool integration

### vs Desktop Session Managers (Crystal, Conductor)
**Desktop Tools**: Rich UI but requires context switching from terminal
**Cafedelia**: Terminal-native with equivalent functionality, preserves developer flow

### vs Terminal Chat Tools (All Rust/Ratatui-based)
**Rust Tools**: Basic chat interfaces, no session management
**Cafedelia**: Textual framework + session intelligence + workflow orchestration

### vs Direct Claude Code Usage
**Claude Code**: Powerful agent, primitive session management
**Cafedelia**: Same power + visual session management + intelligence layer + coordination

## Success Criteria

### Functional Success
- [ ] Browse and attach to existing Claude Code sessions visually
- [ ] Create new sessions with project/branch context
- [ ] Embed tmux sessions seamlessly in Textual interface
- [ ] Monitor background session progress with summaries

### Experience Success
- [ ] Zero context switching from terminal environment
- [ ] Faster session discovery than manual `claude code --resume`
- [ ] Background session awareness improves workflow efficiency
- [ ] Professional UI that developers want to use daily

### Adoption Success
- [ ] Terminal-native developers choose Cafedelia over desktop alternatives
- [ ] Teams use Cafedelia for coordinated AI development workflows
- [ ] Community contributions to CLI provider ecosystem
- [ ] Recognition as premier terminal AI session manager

## Long-Term Vision

### Near Term (6 months)
- Claude Code integration with session management
- Beautiful terminal UI with tmux embedding
- Basic session discovery and attachment

### Medium Term (1 year)  
- Multiple CLI provider support (Aider, other tools)
- Advanced session intelligence with cross-session coordination
- Git worktree automation and branch management

### Long Term (2+ years)
- Full AI workflow orchestration platform
- Team collaboration features
- Integration ecosystem with developer tools
- Industry standard for terminal AI session management

Cafedelia transforms the terminal AI development experience from isolated conversations to orchestrated workflow management while preserving the beautiful, professional interface that makes tools like Elia a joy to use.
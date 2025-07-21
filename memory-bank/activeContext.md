# Active Context

## Current State  
- **Date**: July 21, 2025
- **Focus**: Claude Code GUI Wrapper Development 
- **Status**: Standalone Cafedelia complete, focusing on Claude Code integration

## Cafedelia Fork Strategy (July 20, 2025)

### Strategic Decision: Focus Exclusively on Claude Code
**Rationale**: Build the GUI that Claude Code should have had from the beginning - complete session management and intelligence

**What We Get Free from Elia**:
- Beautiful, functional Textual interface
- Robust configuration system for models
- SQLite persistence for session tracking
- Professional screen management and navigation
- Theme system and customization

**What We Add for Claude Code**:
- Visual session browser and management
- Claude Code session discovery from filesystem
- Tmux integration for session embedding
- Session intelligence and progress monitoring
- Model configuration GUI for Claude Code's available models

### Fork Analysis Complete
**Elia Architecture Assessment**: ✅
- `config.py`: EliaChatModel system perfect for extension
- `widgets/chat_options.py`: Ideal injection point for provider type selection
- `screens/chat_screen.py`: Target for CLI provider interface replacement
- `database/`: SQLite patterns ready for session management

### Implementation Approach Defined
**Phase 1**: Claude Code Model Configuration
- Configure available Claude Code models in Elia's model system
- Replace API provider models with Claude Code model selection
- Create GUI for Claude Code model configuration

**Phase 2**: Session Discovery and Management
- Implement Claude Code session discovery from `~/.claude/__store.db`
- Create visual session browser in main interface
- Add session creation/attachment logic with tmux integration

**Phase 3**: Session Intelligence and Monitoring
- Background session progress monitoring
- Session status and health indicators
- Project-based session organization

## Current Development Focus

### Immediate Priority: Memory Bank Setup
**Status**: In Progress - Creating foundational documentation
- [x] Project brief adapted for Elia fork approach
- [x] Product context explaining the gap Cafedelia fills
- [ ] System patterns for Elia extension architecture  
- [ ] Technical context for development setup
- [ ] Progress tracking for implementation phases

### Next Development Phase: Claude Code Model Integration
**Target**: Configure Claude Code models as primary interface

```python
# Current Elia: General LLM model selection
with RadioSet(id="available-models"):
    # OpenAI, Anthropic, Google models

# Cafedelia: Claude Code models from configuration
with RadioSet(id="claude-code-models"):
    ○ Claude 3.5 Sonnet (Latest)
    ● Claude 3.5 Haiku (Fast) 
    ○ Claude 3 Opus (Most Capable)
```

### Technical Roadmap Priorities
1. **Claude Code Model Configuration** (Week 1)
   - Configure Claude Code models in EliaChatModel system
   - Replace default models with Claude Code model selection
   - Create model configuration GUI for Claude Code settings

2. **Session Discovery** (Week 2)  
   - Implement Claude Code session discovery from `~/.claude/__store.db`
   - Parse session metadata and sync to Cafedelia database
   - Create visual session browser interface

3. **Session Management** (Week 3)
   - Build session attachment and creation logic
   - Implement tmux integration for session display
   - Add session status monitoring and health checks

4. **Session Intelligence** (Week 4+)
   - Background session progress monitoring
   - Session summaries and achievement tracking
   - Project-based session organization

## Technical Context

### Development Environment
- **Base**: Forked Elia repository at `/home/alex/code/cafedelia`
- **Framework**: Python Textual for terminal UI
- **Configuration**: Extends Elia's TOML-based model system
- **Database**: SQLite for session tracking and intelligence

### Key Extension Points Identified
- **EliaChatModel**: Add provider_type, cli_command, session_manager fields
- **OptionsModal**: Inject provider type selection UI
- **ChatScreen**: Route to TmuxSession widget for CLI providers
- **Configuration**: Add CLI provider definitions to builtin models

### Unique Market Position
**Cafedelia = Elia's UI Polish + Claude Code's Power + Session Intelligence**
- Only Textual-based terminal LLM tool (vs ubiquitous Rust/Ratatui)
- Terminal-native session management (vs desktop-only Crystal/Conductor)
- Intelligence layer for workflow orchestration (vs basic chat interfaces)

## Previous Research Insights (Context)

### Competitive Landscape Validation
**Terminal LLM Tools**: All use Rust/Ratatui framework
- AIChat: CLI/REPL interface
- Oatmeal: Ratatui with chat bubbles
- Tenere: Ratatui with vim keybindings
- parllama: Ratatui for Ollama management

**Insight**: Textual framework creates unique positioning opportunity

### Session Management Tools Analysis
**Desktop Solutions**:
- **Crystal**: Multiple Claude Code instances with git worktrees (Electron)
- **Conductor**: Claude Code workspace collaboration (Desktop)

**Gap**: No terminal-native equivalent with equivalent functionality

### Git Worktree + AI Sessions Pattern
**2024-2025 Developer Consensus**: "Git worktrees + AI assistant has been an absolute game changer"
- Each worktree maintains isolated Claude Code context
- Parallel development without context switching
- Preserves AI's deep codebase understanding

**Validation**: Cafedelia's approach aligns with proven workflow patterns

## Next Actions

### Immediate (This Week)
1. **Complete Memory Bank Setup**: Finish system patterns, tech context, progress docs
2. **Provider Architecture Design**: Detailed technical specification for CLI provider support
3. **Elia Codebase Deep Dive**: Identify exact modification points for provider type separation

### Short Term (Next 2 Weeks)
1. **Implement Provider Type Selection**: Extend OptionsModal with API vs CLI separation
2. **Claude Code Provider Definition**: Add CLI provider configuration to models
3. **Session Discovery Prototype**: Basic Claude Code session scanning functionality

### Medium Term (Next Month)
1. **Tmux Integration**: Working session embedding in Textual interface
2. **Session Management UI**: Complete session browser and attachment logic
3. **Intelligence Foundation**: Basic background monitoring capabilities

## Key Decisions Made

### Architecture: Incremental Enhancement vs Rewrite
**Decision**: Fork and extend Elia rather than build from scratch
**Rationale**: Proven UI patterns, robust configuration system, faster time to value

### Provider Pattern: Extension vs Replacement  
**Decision**: Extend existing EliaChatModel system with provider_type field
**Rationale**: Preserve Elia's excellent configuration patterns while adding CLI support

### UI Strategy: Screen Routing vs Widget Replacement
**Decision**: Route CLI providers to different widgets/screens vs modifying chat interface
**Rationale**: Clean separation of concerns, preserves API provider functionality

### Session Strategy: Tmux Integration vs Terminal Emulation
**Decision**: Embed tmux sessions rather than reimplement terminal functionality
**Rationale**: Leverage proven terminal multiplexing, preserve existing developer workflows

The foundation is set for transforming Elia into the comprehensive AI session management platform that the terminal development community needs.
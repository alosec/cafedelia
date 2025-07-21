# Active Context

## Current State  
- **Date**: July 21, 2025
- **Focus**: UI/UX Optimization - Chatbox Performance and History Widget Improvements
- **Status**: Hybrid architecture complete, optimizing user experience and performance

## Cafedelia Fork Strategy (July 20, 2025)

### Strategic Decision: Fork Elia Instead of Building from Scratch
**Rationale**: Leverage proven Textual UI framework and configuration system while adding CLI provider capabilities

**What We Get Free**:
- Beautiful, functional Textual interface
- Robust model/provider configuration system  
- SQLite persistence and chat history
- Professional screen management and navigation
- Theme system and customization
- TOML configuration patterns

**What We Add**:
- CLI provider support alongside API providers
- Claude Code session discovery and management
- Tmux integration for terminal session embedding
- Background session monitoring with intelligence layer

### Fork Analysis Complete
**Elia Architecture Assessment**: ✅
- `config.py`: EliaChatModel system perfect for extension
- `widgets/chat_options.py`: Ideal injection point for provider type selection
- `screens/chat_screen.py`: Target for CLI provider interface replacement
- `database/`: SQLite patterns ready for session management

### Implementation Approach Defined
**Phase 1**: Provider Type Separation in OptionsModal
- Extend UI to distinguish "API Providers" vs "CLI Providers"  
- Modify EliaChatModel to support provider_type field
- Add Claude Code as first CLI provider definition

**Phase 2**: CLI Provider Architecture
- Create TmuxSession widget to replace Chat widget for CLI providers
- Implement Claude Code session discovery from filesystem
- Add session creation/attachment logic with tmux integration

**Phase 3**: Session Intelligence Layer
- Background session monitoring
- `claude -p` integration for session summaries
- Cross-session coordination capabilities

## Current Development Focus

### CRITICAL DISCOVERY: Claude Code Data Architecture Change (July 21, 2025)
**Major Finding**: Claude Code abandoned SQLite (`~/.claude/__store.db`) in favor of per-project JSONL files (`~/.claude/projects/[project]/[session-id].jsonl`)
- Our direct database integration was reading **deprecated data** (only sessions from May 2025)
- **Current sessions live in JSONL format** with rich metadata and real-time updates
- **Architecture pivot required**: Hybrid approach combining JSONL sync + live Claude Code integration

### Hybrid Architecture IMPLEMENTED ✅
**Browse Mode**: JSONL → SQLite sync for historical sessions (319 sessions discovered)  
**Live Mode**: Claude Code CLI integration with `claude -p --output-format stream-json`

**CLI Integration Features**:
- Uses Claude Code subscription billing (no API key required)
- Structured JSON streaming: `claude -p --output-format stream-json`
- Session resumption: `claude -p --resume session_id`
- Proper message parsing according to Claude Code schema
- Real-time streaming with cost/timing metadata

### COMPLETED: Dual-Mode Implementation ✅
**Status**: Hybrid architecture fully implemented and functional
- [x] Git revert to clean cafedelia.sqlite foundation (commit 9b0f54d)
- [x] Memory bank updated with new hybrid approach  
- [x] Create sync directory structure for JSONL processing
- [x] Implement Claude Code CLI wrapper for live chat (uses subscription billing)
- [x] Build JSONL watcher and transformer for historical data
- [x] CLI-based integration with `claude -p --output-format stream-json`
- [x] Session resumption with `claude -p --resume session_id`
- [x] Structured JSON parsing according to Claude Code message schema

### MAJOR BREAKTHROUGH: JSONL Message Parsing ✅ COMPLETED (July 21, 2025)
**Status**: Complete success - message grouping and content extraction working excellently

#### ✅ SOLVED: Message Parsing Issues
1. **Message Grouping**: Successfully implemented message threading that groups assistant messages with their tool results
2. **Rich Content Extraction**: Tool calls now show actual commands, parameters, and full reasoning context
3. **Complete Conversation Flow**: Users see full thought process + tool usage + results in coherent format

#### Rendering Quality Achieved
- **Before**: `[Used tool: Bash (toolu_01...)]` + separate `[Tool result: ...]` messages  
- **After**: Complete conversation flows with reasoning, tool calls with parameters, and formatted results
- **User Feedback**: "Quite excellent", "absolutely fantastic", "exactly what I was looking for"
- **Information Density**: Shows more detail than Claude Code's interactive interface

### CURRENT PRIORITY: Live Chat Functionality
**Focus**: Improve robustness of real-time Claude Code CLI integration

#### Known Issues with Live Chat
- Live messaging functionality not working robustly
- Need to investigate streaming and real-time response handling
- Current implementation may have reliability issues with `claude -p` integration

```python
# Current Elia: Single model selection
with RadioSet(id="available-models"):
    # All models listed together

# Cafedelia: Provider type separation  
with RadioSet(id="provider-types"):
    ○ API Providers    # OpenAI, Anthropic, Google
    ● CLI Providers    # Claude Code, future tools
```

### Technical Roadmap Priorities
1. **Message Parsing Improvements** (Week 1)
   - Fix blank agent messages from tool call parsing failures
   - Enhance JSON message parsing for complex Claude Code responses
   - Add proper handling for tool results and system messages

2. **History Widget Optimization** (Week 1-2)
   - Implement lazy loading for session discovery
   - Add pagination or virtual scrolling for large datasets
   - Create filtering and search capabilities for sessions
   - Optimize database queries for session metadata

3. **Chatbox UI Enhancement** (Week 2)
   - Improve chatbox responsiveness and visual feedback
   - Add proper loading states for streaming responses
   - Optimize message display for long conversations
   - Enhance error handling and user feedback

4. **Performance Architecture** (Week 3+)
   - Background session indexing and caching
   - Efficient session state management
   - Memory optimization for large session datasets
   - Progressive loading strategies

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
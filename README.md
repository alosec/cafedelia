# Cafedelia - Terminal AI Session Management

Cafedelia transforms the terminal AI development experience from isolated conversations to orchestrated workflow management. Built as a strategic fork of [Elia](https://github.com/darrenburns/elia), it combines Elia's beautiful Textual interface with serious Claude Code session management capabilities.

## Architecture: Elia UI + Cafed Backend

```
┌─────────────────────────────────────┐
│           CAFEDELIA UI              │
│         (Elia Textual)              │
│  ┌─────────────────────────────────┐ │
│  │ Screens: Home, Chat, Sessions   │ │
│  │ Widgets: Session Browser,       │ │
│  │          Intelligence Display   │ │
│  │ Database: Extended Elia Schema  │ │
│  └─────────────────────────────────┘ │
└─────────────┬───────────────────────┘
              │ HTTP/WebSocket API
              ▼
┌─────────────────────────────────────┐
│           CAFED BACKEND             │
│       (TypeScript Express)          │
│  ┌─────────────────────────────────┐ │
│  │ WTE Pipeline:                   │ │
│  │ - Watch: ~/.claude/projects/    │ │
│  │ - Transform: JSONL → Elia       │ │
│  │ - Execute: Database Updates     │ │
│  │                                 │ │
│  │ Services:                       │ │
│  │ - Claude Discovery              │ │
│  │ - Session Intelligence          │ │
│  │ - Project Organization          │ │
│  └─────────────────────────────────┘ │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│     ~/.claude/projects/             │
│   ┌─── project-uuid-1/ ──────────┐   │
│   │   session-abc123.jsonl      │   │
│   │   session-def456.jsonl      │   │
│   └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

## What Makes Cafedelia Different

### vs Pure Elia
- **Workflow Management**: Real AI session orchestration vs simple chat
- **CLI Tool Integration**: Bridge to powerful development tools like Claude Code
- **Session Persistence**: Background session management vs ephemeral conversations

### vs Desktop Session Managers (Crystal, Conductor) 
- **Terminal-Native**: No context switching from developer environment
- **Textual Framework**: Rich terminal UI capabilities with professional polish
- **Integration Depth**: Native Claude Code filesystem integration

### vs Other Terminal LLM Tools
- **Framework Choice**: Textual vs ubiquitous Rust/Ratatui alternatives
- **Session Focus**: Intelligence layer for workflow management vs simple chat interfaces
- **Extensible Backend**: TypeScript Express backend with Watch-Transform-Execute pipeline

## Key Features (Implemented)

### 🔧 Hybrid Architecture
- **Elia Frontend**: Proven Textual interface with beautiful themes and navigation
- **Cafed Backend**: TypeScript Express server with Claude Code integration
- **Bridge Layer**: Python HTTP client connecting UI to backend services

### 📁 Claude Code Discovery
- **Session Scanning**: Automatic discovery of ~/.claude/projects/ sessions
- **JSONL Parsing**: Extract conversation turns, costs, file operations from session logs
- **Project Organization**: Decode Claude's directory encoding to filesystem paths

### 💾 Database Integration
- **Extended Schema**: New tables for Claude Code session tracking
- **Session Intelligence**: AI-generated summaries and insights
- **Relationship Mapping**: Link Claude sessions to Elia chat conversations

### 🔄 Real-time Synchronization
- **Session Sync**: Background sync between cafed backend and Elia database  
- **Health Monitoring**: Backend process management and health checks
- **Intelligence Updates**: Track session progress and file operations

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Claude Code CLI installed and used (creates ~/.claude/projects/)

### Installation

```bash
# Clone cafedelia repository
git clone https://github.com/alosec/cafedelia.git
cd cafedelia

# Install Python dependencies
pip install -e .

# Setup backend (installs Node.js deps and builds TypeScript)
./scripts/setup-cafed.sh
```

### Usage

```bash
# Start Cafedelia (automatically starts cafed backend)
cafedelia

# Or use elia command for compatibility
elia
```

The application will:
1. Start the cafed backend server on port 8001
2. Scan ~/.claude/projects/ for existing sessions
3. Sync session data to local SQLite database
4. Display sessions alongside regular Elia chats

## Development

### Backend Development

```bash
# Start backend in development mode
cd cafed
npm run dev

# Build TypeScript
npm run build

# Type checking
npm run type-check
```

### API Endpoints

The cafed backend provides REST API endpoints:

- `GET /health` - Health check
- `GET /api/sessions` - List all Claude Code sessions
- `GET /api/sessions/:id` - Get specific session
- `GET /api/projects` - List all projects
- `GET /api/summary` - Session summary statistics

### Database Migrations

Cafedelia extends Elia's database schema:

```sql
-- New tables for Claude Code integration
CREATE TABLE claude_session (
    session_uuid TEXT UNIQUE,
    project_name TEXT,
    project_path TEXT, 
    status TEXT,
    conversation_turns INTEGER,
    total_cost_usd REAL,
    file_operations JSON,
    intelligence_summary TEXT,
    -- ... timestamps, relationships
);

CREATE TABLE session_intelligence (
    session_uuid TEXT,
    summary_type TEXT,
    summary_content TEXT,
    confidence_score REAL,
    -- ... metadata
);
```

## Project Structure

```
cafedelia/
├── elia_chat/                    # Elia UI (inherited + extensions)
│   ├── app.py                   # Main app with cafed integration  
│   ├── database/
│   │   ├── models.py            # Extended with Claude session models
│   │   └── migrations/          # Database schema updates
│   └── screens/                 # UI screens (home, chat, sessions)
│
├── cafed/                       # TypeScript backend
│   ├── core/                    # WTE pipeline interfaces
│   ├── services/                # Claude discovery and session services
│   ├── api/                     # HTTP API routes
│   ├── database/                # Path mappings and utilities
│   └── index.ts                 # Express server entry point
│
├── bridge/                      # Python ↔ TypeScript bridge
│   ├── cafed_client.py         # HTTP client for backend API
│   └── session_sync.py         # Database synchronization
│
└── scripts/                     # Management and setup scripts
    ├── setup-cafed.sh          # Install and build backend
    └── start-cafed.sh          # Start backend server
```

## Technical Implementation

### Watch-Transform-Execute Pipeline

```typescript
interface WTE<T, A> {
  watch: () => AsyncGenerator<T>;      // Watch JSONL files
  transform: (event: T) => A | null;   // Transform to Elia format  
  execute: (action: A) => Promise<void>; // Update Elia database
}
```

### Session Discovery

```typescript
class ClaudeDiscovery {
  // Scan ~/.claude/projects/ directories
  async findAllProjects(): Promise<ClaudeProject[]>
  
  // Parse JSONL session files
  async parseSessionFile(path: string): Promise<ClaudeSession>
  
  // Decode Claude's path encoding
  decodeProjectPath(encoded: string): string
}
```

### Database Bridge

```python
class SessionSync:
  # Sync all sessions from backend to database
  async sync_all_sessions() -> dict
  
  # Add intelligence summaries
  async add_intelligence(session_uuid: str, summary: str)
  
  # Health check both systems
  async health_check() -> dict
```

## Roadmap

### Phase 1: Core Integration ✅
- [x] Hybrid architecture setup
- [x] Claude Code session discovery  
- [x] Database schema extensions
- [x] Backend API implementation
- [x] Python-TypeScript bridge

### Phase 2: UI Integration (In Progress)
- [ ] Session browser widget
- [ ] Intelligence display widget  
- [ ] Session management screen
- [ ] Real-time session monitoring

### Phase 3: Advanced Features (Planned)
- [ ] Watch-Transform-Execute pipeline for live updates
- [ ] Session intelligence with AI summaries
- [ ] Cross-session task delegation
- [ ] Git worktree integration

### Phase 4: Ecosystem (Future)
- [ ] Additional CLI provider support (Aider, other tools)
- [ ] MCP (Model Context Protocol) integration
- [ ] Team collaboration features
- [ ] Plugin ecosystem

## Philosophy

**"The session intelligence layer that should have existed from the beginning"**

Cafedelia bridges the gap between beautiful terminal chat tools (like Elia) and powerful CLI agents (like Claude Code) by adding the missing session management and intelligence layer. It preserves developer flow while adding serious workflow orchestration capabilities.

## Contributing

Cafedelia builds on the excellent foundation of [Elia](https://github.com/darrenburns/elia) by Darren Burns. We maintain compatibility with Elia's patterns while extending capabilities for AI session management.

## License

Licensed under the same terms as Elia. See LICENSE file for details.

---

*Transform your terminal AI development experience with Cafedelia - where beautiful interfaces meet serious workflow management.*

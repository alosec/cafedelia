# Project Intelligence (.clauderules)

## Critical Rules

### Application Execution
**NEVER run the interactive textual app under any circumstances.**
- Do NOT use bash tool to run `python -m elia_chat`
- Do NOT use bash tool to run `elia_chat.py`  
- Do NOT use bash tool to run any interactive TUI applications
- Testing should be limited to syntax validation and import checks only

## Development Context

### Virtual Environment
- Location: `/home/alex/code/cafedelia/.venv`
- Activation: `source /home/alex/code/cafedelia/.venv/bin/activate`
- Database: SQLite at `/home/alex/code/cafedelia/cafedelia.sqlite`

### Key Technologies
- **TUI Framework**: Textual (Python)
- **Database**: SQLAlchemy with SQLite
- **Architecture**: Async/await patterns throughout
- **Import System**: JSONL files in `~/.claude/projects/` for Claude Code sessions

### Widget Architecture
- **ChatList**: Primary chat history widget (preferred over SessionsWidget)
- **SessionsWidget**: Legacy widget being phased out
- **HomeScreen**: Main application screen using ChatList
- **Event System**: Message-based communication between widgets

### Recent Changes
- **Strategic Pivot to Robust Sync**: Moving from simple import to production-grade bidirectional synchronization
- **Data Integrity Issues Discovered**: Current sync creates duplicates, uses fake models, vulnerable to race conditions
- **New Architecture Direction**: Bulletproof sync with atomic operations, distributed locking, conflict resolution

## Sync Architecture Intelligence

### Current Sync System Issues
- **Race Conditions**: JSONL files read while Claude Code is writing, causing corruption
- **Duplicate Creation**: Bridge creates new sessions instead of updating existing ones  
- **Fake Data Override**: Bridge replaces real JSONL titles/models with generic fake data
- **No Distributed Locking**: Multiple sync processes can corrupt database state
- **No Transaction Safety**: Interrupted operations leave database inconsistent

### Required Robustness Components
- **Atomic Write Detection**: Wait for JSONL file completion before processing
- **Change Detection**: File signatures to avoid unnecessary processing
- **Conflict Resolution**: JSONL wins for content, database for UI metadata
- **Distributed Locks**: File-based locking to prevent concurrent access
- **Transaction Management**: Rollback capabilities for failed operations
- **Circuit Breaker**: Graceful degradation when backend/network fails

### Database Locations
- **Development**: `/home/alex/code/cafedelia/cafedelia.sqlite` (empty)
- **Actual Data**: `~/.local/share/cafedelia/cafedelia.sqlite` (production data)
- **Backend API**: Docker container `cafedelia-backend` on port 8001

## Testing Approach
- Use syntax validation instead of running the app
- Import checks for module verification  
- Database operations require async context managers
- User tests application independently in their own terminal
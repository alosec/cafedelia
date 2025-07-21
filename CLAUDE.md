# Cafedelia Development Environment

## Project Overview
Cafedelia is a Python TUI (Terminal User Interface) chat application for browsing and interacting with Claude Code sessions.

## Development Setup

### Virtual Environment
- **Location**: `/home/alex/code/cafedelia/.venv`
- **Activation**: `source /home/alex/code/cafedelia/.venv/bin/activate`
- **Dependencies**: SQLAlchemy, asyncio, textual for TUI

### Database
- **Location**: `~/.local/share/cafedelia/cafedelia.sqlite`
- **Type**: SQLite with async support
- **Tables**: `chat`, `message`, `system_prompt`
- **Note**: Database operations require async context managers

### Key Commands
```bash
# Activate virtual environment
source /home/alex/code/cafedelia/.venv/bin/activate

# Run the application
python -m elia_chat

# Run database migrations
python -m elia_chat.database.migrations.<migration_name>

# Run tests
python -m pytest tests/

# Direct database access
sqlite3 ~/.local/share/cafedelia/cafedelia.sqlite
```

### Architecture Notes
- **Source of Truth**: JSONL files in `~/.claude/projects/` contain authoritative Claude Code session data
- **Database Role**: Performance layer for fast chat browsing and search
- **Sync Process**: Background service syncs JSONL → SQLite with deduplication
- **Live Chat**: Direct subprocess integration with Claude Code CLI

### Common Database Operations
```sql
-- Check chat count
SELECT COUNT(*) FROM chat;

-- Check for duplicates
SELECT title, COUNT(*) FROM chat GROUP BY title HAVING COUNT(*) > 1;

-- Clean up duplicates (keep earliest)
DELETE FROM chat WHERE id NOT IN (SELECT MIN(id) FROM chat GROUP BY title);

-- Clean up orphaned messages
DELETE FROM message WHERE chat_id NOT IN (SELECT id FROM chat);
```

### Troubleshooting
- Always activate venv before Python commands
- Database corruption: Delete `~/.local/share/cafedelia/cafedelia.sqlite` to rebuild from JSONL
- Sync issues: Check deduplication service logs and session_id uniqueness
# Cafedelia Reactive Updates & Session Persistence Fix

## Summary of Changes

This refactoring addresses the issue where Claude Code streaming responses display correctly in the UI but don't persist to the database. The fix implements:

1. **SQLite WAL Mode** - Enables concurrent read/write operations
2. **Textual Reactive Attributes** - Automatic UI updates without manual refresh
3. **Session ID Persistence** - Proper storage and retrieval of Claude Code session IDs

## Key Changes

### Database Layer
- Added WAL (Write-Ahead Logging) mode to SQLite for better concurrency
- Added `find_by_session_id` method to prevent duplicate sessions
- Updated `create_chat` to include session_id field
- Added `update_chat_session_id` method for post-creation updates

### UI Layer  
- Added reactive `content` attribute to Chatbox widget
- Removed manual `refresh()` calls - reactive attributes handle updates
- Proper session ID capture and persistence during streaming

### Session Management
- Session IDs now properly persist to database during chat creation
- Updates propagate through reactive system automatically
- No more "saves on reload but not during streaming" issues

## Testing

1. Run migrations: `python run_migrations.py`
2. Run tests: `python test_reactive_updates.py`
3. Launch app: `python -m elia_chat`
4. Start a Claude Code chat and observe:
   - Streaming updates appear immediately
   - Content persists to database in real-time
   - Session IDs are saved and can be resumed

## Technical Details

The reactive system works by:
- `content = reactive("", layout=True)` triggers UI updates on change
- `append_chunk()` modifies reactive attribute → automatic refresh
- WAL mode allows UI to read while streaming writes occur
- Session ID captured via message passing and persisted to DB

This creates a seamless experience where streaming Claude Code responses both display and persist correctly.

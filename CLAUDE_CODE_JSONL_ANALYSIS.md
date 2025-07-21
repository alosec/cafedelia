# Claude Code JSONL to Elia Database Transformation Analysis

## Executive Summary

This document provides a comprehensive technical analysis of the Claude Code JSONL format and the exact transformation requirements for integration with Elia's SQLite database schema. The analysis covers data structures, field mappings, transformation logic, and real-time synchronization patterns.

## JSONL Format Analysis

### Structure Overview

Claude Code stores conversation data in JSONL (JSON Lines) format where each line represents a single event or message in the conversation timeline. Files are organized by project directory and session ID:

```
~/.claude/projects/
├── -home-alex-code-project/
│   ├── session-uuid-1.jsonl
│   ├── session-uuid-2.jsonl
│   └── ...
└── -other-project-path/
    └── session-files.jsonl
```

### Message Types

#### 1. Summary Messages
```json
{
  "type": "summary",
  "summary": "Conversation title/summary",
  "leafUuid": "uuid-pointing-to-final-message"
}
```

#### 2. User Messages
```json
{
  "parentUuid": "uuid-of-parent-message",
  "isSidechain": false,
  "userType": "external",
  "cwd": "/working/directory",
  "sessionId": "session-uuid",
  "version": "1.0.56",
  "gitBranch": "main",
  "type": "user",
  "message": {
    "role": "user",
    "content": "text" | [{"type": "text", "text": "content"}]
  },
  "isMeta": true|false,
  "uuid": "message-uuid",
  "timestamp": "2025-07-21T00:28:54.245Z"
}
```

#### 3. Assistant Messages
```json
{
  "parentUuid": "uuid-of-parent-message",
  "isSidechain": false,
  "userType": "external",
  "cwd": "/working/directory",
  "sessionId": "session-uuid",
  "version": "1.0.56",
  "gitBranch": "main",
  "message": {
    "id": "msg_anthropic_id",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-4-20250514",
    "content": [
      {
        "type": "text",
        "text": "Response text"
      },
      {
        "type": "tool_use",
        "id": "tool_id",
        "name": "ToolName",
        "input": { "param": "value" }
      }
    ],
    "stop_reason": "stop_sequence",
    "stop_sequence": null,
    "usage": {
      "input_tokens": 4,
      "cache_creation_input_tokens": 5367,
      "cache_read_input_tokens": 10367,
      "output_tokens": 5,
      "service_tier": "standard"
    }
  },
  "requestId": "req_anthropic_id",
  "type": "assistant",
  "uuid": "message-uuid",
  "timestamp": "2025-07-21T00:28:57.369Z"
}
```

#### 4. Tool Result Messages (User-type)
```json
{
  "parentUuid": "tool-use-message-uuid",
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "tool_use_id": "tool_id",
        "type": "tool_result",
        "content": "Tool execution result"
      }
    ]
  },
  "uuid": "result-message-uuid",
  "timestamp": "2025-07-21T00:28:59.645Z",
  "toolUseResult": "Result text"
}
```

## Elia Database Schema

### Core Tables

#### base_messages
```sql
CREATE TABLE `base_messages` (
    `uuid` text PRIMARY KEY NOT NULL,
    `parent_uuid` text,
    `session_id` text NOT NULL,
    `timestamp` integer NOT NULL,
    `message_type` text NOT NULL,
    `cwd` text NOT NULL,
    `user_type` text NOT NULL,
    `version` text NOT NULL,
    `isSidechain` integer NOT NULL,
    `original_cwd` text NOT NULL DEFAULT '',
    FOREIGN KEY (`parent_uuid`) REFERENCES `base_messages`(`uuid`)
);
```

#### assistant_messages
```sql
CREATE TABLE `assistant_messages` (
    `uuid` text PRIMARY KEY NOT NULL,
    `cost_usd` real NOT NULL,
    `duration_ms` integer NOT NULL,
    `message` text NOT NULL,
    `is_api_error_message` integer DEFAULT false NOT NULL,
    `timestamp` integer NOT NULL,
    `model` text DEFAULT '' NOT NULL,
    FOREIGN KEY (`uuid`) REFERENCES `base_messages`(`uuid`)
);
```

#### user_messages
```sql
CREATE TABLE `user_messages` (
    `uuid` text PRIMARY KEY NOT NULL,
    `message` text NOT NULL,
    `tool_use_result` text,
    `timestamp` integer NOT NULL,
    `is_at_mention_read` integer,
    `is_meta` integer,
    FOREIGN KEY (`uuid`) REFERENCES `base_messages`(`uuid`)
);
```

#### conversation_summaries
```sql
CREATE TABLE `conversation_summaries` (
    `leaf_uuid` text PRIMARY KEY NOT NULL,
    `summary` text NOT NULL,
    `updated_at` integer NOT NULL,
    FOREIGN KEY (`leaf_uuid`) REFERENCES `base_messages`(`uuid`)
);
```

## Field Mapping Analysis

### JSONL to base_messages
```python
jsonl_record -> base_messages:
    uuid: jsonl.uuid
    parent_uuid: jsonl.parentUuid
    session_id: jsonl.sessionId
    timestamp: parse_iso_to_unix(jsonl.timestamp)
    message_type: jsonl.type  # "user" | "assistant"
    cwd: jsonl.cwd
    user_type: jsonl.userType
    version: jsonl.version
    isSidechain: int(jsonl.isSidechain)
    original_cwd: jsonl.get("originalCwd", jsonl.cwd)
```

### JSONL to user_messages
```python
user_jsonl_record -> user_messages:
    uuid: jsonl.uuid
    message: json.dumps(jsonl.message)  # Serialize entire message object
    tool_use_result: jsonl.get("toolUseResult")
    timestamp: parse_iso_to_unix(jsonl.timestamp)
    is_at_mention_read: jsonl.get("isAtMentionRead")
    is_meta: int(jsonl.get("isMeta", False))
```

### JSONL to assistant_messages
```python
assistant_jsonl_record -> assistant_messages:
    uuid: jsonl.uuid
    cost_usd: calculate_cost_from_usage(jsonl.message.usage)
    duration_ms: estimate_duration()  # From request timing
    message: json.dumps(jsonl.message)  # Serialize entire message object
    is_api_error_message: 0  # Default to false
    timestamp: parse_iso_to_unix(jsonl.timestamp)
    model: jsonl.message.model
```

### JSONL to conversation_summaries
```python
summary_jsonl_record -> conversation_summaries:
    leaf_uuid: jsonl.leafUuid
    summary: jsonl.summary
    updated_at: current_unix_timestamp()
```

## Data Transformation Logic

### 1. Timestamp Conversion
```python
def parse_iso_to_unix(iso_timestamp: str) -> int:
    """Convert ISO 8601 timestamp to Unix timestamp"""
    from datetime import datetime
    dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
    return int(dt.timestamp())
```

### 2. Cost Calculation
```python
def calculate_cost_from_usage(usage: dict) -> float:
    """Calculate approximate cost from token usage"""
    # Claude Sonnet 4 pricing (approximate)
    input_cost_per_1k = 0.003  # $3/1M tokens
    output_cost_per_1k = 0.015  # $15/1M tokens
    
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_tokens = usage.get("cache_read_input_tokens", 0)
    
    # Cache tokens are discounted
    effective_input = input_tokens + (cache_tokens * 0.1)  # 90% discount
    
    cost = ((effective_input / 1000) * input_cost_per_1k + 
            (output_tokens / 1000) * output_cost_per_1k)
    
    return round(cost, 6)
```

### 3. Duration Estimation
```python
def estimate_duration(usage: dict, timestamp_diff: int = None) -> int:
    """Estimate response duration in milliseconds"""
    output_tokens = usage.get("output_tokens", 0)
    # Rough estimate: ~50 tokens per second for Claude
    estimated_ms = (output_tokens / 50) * 1000
    
    # Use actual timestamp difference if available
    if timestamp_diff:
        return min(timestamp_diff, 120000)  # Cap at 2 minutes
    
    return max(int(estimated_ms), 100)  # Minimum 100ms
```

### 4. Message Content Parsing
```python
def extract_text_content(message_content) -> str:
    """Extract readable text from Claude API message content"""
    if isinstance(message_content, str):
        return message_content
    
    if isinstance(message_content, list):
        text_parts = []
        for item in message_content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "tool_use":
                    tool_name = item.get("name", "Unknown")
                    text_parts.append(f"[Tool: {tool_name}]")
            elif isinstance(item, str):
                text_parts.append(item)
        return "\n".join(text_parts)
    
    return str(message_content)
```

## Real-time Synchronization Strategy

### 1. File Watching
```python
import watchdog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class JSONLWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.jsonl'):
            asyncio.create_task(sync_jsonl_file(event.src_path))
    
    def on_created(self, event):
        if event.src_path.endswith('.jsonl'):
            asyncio.create_task(sync_jsonl_file(event.src_path))
```

### 2. Incremental Updates
```python
async def sync_jsonl_file(file_path: Path):
    """Sync a JSONL file to database with incremental updates"""
    session_id = file_path.stem
    
    # Track last processed line for incremental updates
    last_line = await get_last_processed_line(session_id)
    
    with open(file_path, 'r') as f:
        # Skip to last processed line
        for _ in range(last_line):
            next(f)
        
        # Process new lines
        for line_num, line in enumerate(f, start=last_line + 1):
            if line.strip():
                record = json.loads(line)
                await process_jsonl_record(record)
                await update_last_processed_line(session_id, line_num)
```

### 3. Upsert Strategy
```python
async def upsert_message(base_msg: BaseMessageDao, 
                        user_msg: UserMessageDao = None,
                        assistant_msg: AssistantMessageDao = None):
    """Insert or update message with conflict resolution"""
    async with get_session() as session:
        # Check if base message exists
        existing = await session.get(BaseMessageDao, base_msg.uuid)
        
        if existing:
            # Update existing record
            for field, value in base_msg.dict(exclude_unset=True).items():
                setattr(existing, field, value)
        else:
            # Insert new record
            session.add(base_msg)
        
        # Handle related messages
        if user_msg:
            await session.merge(user_msg)
        if assistant_msg:
            await session.merge(assistant_msg)
        
        await session.commit()
```

## Session Discovery and Management

### 1. Project-based Session Discovery
```python
async def discover_claude_sessions() -> list[Path]:
    """Discover all Claude Code session files"""
    claude_projects = Path.home() / ".claude" / "projects"
    session_files = []
    
    for project_dir in claude_projects.iterdir():
        if project_dir.is_dir():
            for jsonl_file in project_dir.glob("*.jsonl"):
                session_files.append(jsonl_file)
    
    return sorted(session_files, key=lambda p: p.stat().st_mtime, reverse=True)
```

### 2. Session Metadata Extraction
```python
def extract_session_metadata(file_path: Path) -> dict:
    """Extract metadata from JSONL file path and first few lines"""
    project_path = file_path.parent.name.replace("-", "/")
    session_id = file_path.stem
    
    # Read first few lines for session info
    with open(file_path, 'r') as f:
        first_record = None
        summary_record = None
        
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            
            if record.get("type") == "summary":
                summary_record = record
            elif not first_record:
                first_record = record
            
            # Stop after finding both or reading 10 lines
            if summary_record and first_record:
                break
    
    return {
        "session_id": session_id,
        "project_path": project_path,
        "title": summary_record.get("summary") if summary_record else f"Session {session_id[:8]}",
        "cwd": first_record.get("cwd") if first_record else project_path,
        "git_branch": first_record.get("gitBranch") if first_record else "unknown",
        "last_modified": file_path.stat().st_mtime
    }
```

## Performance Considerations

### 1. Batch Processing
- Process JSONL files in batches of 100 records
- Use database transactions for atomicity
- Implement progress tracking for large files

### 2. Memory Management
- Stream large JSONL files instead of loading entirely into memory
- Use generators for record processing
- Implement garbage collection for temporary objects

### 3. Database Optimization
- Create indexes on session_id, timestamp, parent_uuid
- Use connection pooling for concurrent access
- Implement query result caching for frequently accessed sessions

## Error Handling and Data Validation

### 1. Malformed JSON Handling
```python
def safe_parse_jsonl_line(line: str) -> dict | None:
    """Safely parse JSONL line with error recovery"""
    try:
        return json.loads(line)
    except json.JSONDecodeError as e:
        logger.warning(f"Malformed JSON line: {line[:100]}... Error: {e}")
        return None
```

### 2. Schema Validation
```python
from pydantic import BaseModel, validator

class JSONLRecord(BaseModel):
    uuid: str
    sessionId: str
    timestamp: str
    type: str
    
    @validator('timestamp')
    def validate_timestamp(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {v}")
```

### 3. Data Integrity Checks
```python
async def validate_session_integrity(session_id: str):
    """Validate session data integrity"""
    async with get_session() as session:
        # Check for orphaned messages
        orphaned = await session.exec(
            select(BaseMessageDao)
            .where(BaseMessageDao.session_id == session_id)
            .where(BaseMessageDao.parent_uuid.isnot(None))
            .where(~exists().where(BaseMessageDao.uuid == BaseMessageDao.parent_uuid))
        )
        
        if orphaned:
            logger.warning(f"Found {len(orphaned)} orphaned messages in session {session_id}")
```

## Migration and Deployment Strategy

### 1. Initial Migration
1. **Backup existing Elia database**
2. **Run schema migration** to add Claude Code tables
3. **Import historical JSONL data** in chronological order
4. **Validate data integrity** with checksums
5. **Start real-time sync** with file watchers

### 2. Production Deployment
1. **Feature flag** for Claude Code integration
2. **Gradual rollout** with A/B testing
3. **Monitoring and alerting** for sync errors
4. **Rollback capability** to Elia-only mode

This analysis provides the complete technical foundation for implementing the Claude Code JSONL to Elia database transformation pipeline, enabling real-time session management and intelligent conversation browsing within the Cafedelia interface.
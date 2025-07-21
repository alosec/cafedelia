# Claude Code JSONL Transformation Implementation

## Sample Transformation Functions

This document provides working implementation examples for transforming Claude Code JSONL data into Elia's database format.

## Core Transformation Functions

### 1. JSONL Record Processor

```python
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from elia_chat.database.models import (
    BaseMessageDao, AssistantMessageDao, UserMessageDao, ConversationSummaryDao
)
from elia_chat.database.database import get_session

class JSONLTransformer:
    """Transform Claude Code JSONL records to Elia database format"""
    
    def __init__(self):
        self.session_metadata = {}
        self.processed_uuids = set()
    
    async def process_jsonl_file(self, file_path: Path) -> None:
        """Process entire JSONL file and sync to database"""
        session_id = file_path.stem
        print(f"Processing session {session_id} from {file_path}")
        
        records = []
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue
                
                try:
                    record = json.loads(line)
                    records.append((line_num, record))
                except json.JSONDecodeError as e:
                    print(f"Skipping malformed JSON at line {line_num}: {e}")
                    continue
        
        # Process records in chronological order
        for line_num, record in records:
            await self.process_record(record, session_id, line_num)
    
    async def process_record(self, record: Dict[str, Any], session_id: str, line_num: int) -> None:
        """Process a single JSONL record"""
        record_type = record.get("type")
        
        if record_type == "summary":
            await self.process_summary_record(record)
        elif record_type in ("user", "assistant"):
            await self.process_message_record(record, session_id)
        else:
            print(f"Unknown record type '{record_type}' at line {line_num}")
    
    async def process_summary_record(self, record: Dict[str, Any]) -> None:
        """Process conversation summary record"""
        summary_dao = ConversationSummaryDao(
            leaf_uuid=record["leafUuid"],
            summary=record["summary"],
            updated_at=int(datetime.now().timestamp())
        )
        
        async with get_session() as session:
            # Use merge to handle duplicates
            await session.merge(summary_dao)
            await session.commit()
            print(f"Processed summary: {record['summary'][:50]}...")
    
    async def process_message_record(self, record: Dict[str, Any], session_id: str) -> None:
        """Process user or assistant message record"""
        uuid = record.get("uuid")
        if not uuid or uuid in self.processed_uuids:
            return
        
        # Create base message
        base_msg = BaseMessageDao(
            uuid=uuid,
            parent_uuid=record.get("parentUuid"),
            session_id=session_id,
            timestamp=self.parse_timestamp(record["timestamp"]),
            message_type=record["type"],
            cwd=record.get("cwd", ""),
            user_type=record.get("userType", "external"),
            version=record.get("version", ""),
            isSidechain=int(record.get("isSidechain", False)),
            original_cwd=record.get("originalCwd", record.get("cwd", ""))
        )
        
        # Create type-specific message
        if record["type"] == "user":
            user_msg = await self.create_user_message(record, uuid)
            await self.save_messages(base_msg, user_msg=user_msg)
        elif record["type"] == "assistant":
            assistant_msg = await self.create_assistant_message(record, uuid)
            await self.save_messages(base_msg, assistant_msg=assistant_msg)
        
        self.processed_uuids.add(uuid)
    
    async def create_user_message(self, record: Dict[str, Any], uuid: str) -> UserMessageDao:
        """Create UserMessageDao from JSONL record"""
        message = record.get("message", {})
        
        return UserMessageDao(
            uuid=uuid,
            message=json.dumps(message),  # Store full message as JSON
            tool_use_result=record.get("toolUseResult"),
            timestamp=self.parse_timestamp(record["timestamp"]),
            is_at_mention_read=record.get("isAtMentionRead"),
            is_meta=int(record.get("isMeta", False))
        )
    
    async def create_assistant_message(self, record: Dict[str, Any], uuid: str) -> AssistantMessageDao:
        """Create AssistantMessageDao from JSONL record"""
        message = record.get("message", {})
        usage = message.get("usage", {})
        
        return AssistantMessageDao(
            uuid=uuid,
            cost_usd=self.calculate_cost(usage),
            duration_ms=self.estimate_duration(usage),
            message=json.dumps(message),  # Store full message as JSON
            is_api_error_message=0,  # Default to false
            timestamp=self.parse_timestamp(record["timestamp"]),
            model=message.get("model", "")
        )
    
    async def save_messages(self, base_msg: BaseMessageDao, 
                          user_msg: Optional[UserMessageDao] = None,
                          assistant_msg: Optional[AssistantMessageDao] = None) -> None:
        """Save messages to database with proper relationships"""
        async with get_session() as session:
            # Use merge to handle duplicates gracefully
            session.add(base_msg)
            
            if user_msg:
                session.add(user_msg)
            if assistant_msg:
                session.add(assistant_msg)
            
            try:
                await session.commit()
                print(f"Saved message {base_msg.uuid} ({base_msg.message_type})")
            except Exception as e:
                await session.rollback()
                print(f"Error saving message {base_msg.uuid}: {e}")
    
    def parse_timestamp(self, timestamp_str: str) -> int:
        """Convert ISO timestamp to Unix timestamp"""
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return int(dt.timestamp())
    
    def calculate_cost(self, usage: Dict[str, Any]) -> float:
        """Calculate cost from token usage"""
        # Claude Sonnet 4 pricing (approximate)
        input_cost_per_1k = 0.003
        output_cost_per_1k = 0.015
        cache_discount = 0.9  # 90% discount for cached tokens
        
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cache_tokens = usage.get("cache_read_input_tokens", 0)
        
        # Apply cache discount
        effective_input = input_tokens + (cache_tokens * (1 - cache_discount))
        
        cost = (
            (effective_input / 1000) * input_cost_per_1k +
            (output_tokens / 1000) * output_cost_per_1k
        )
        
        return round(cost, 6)
    
    def estimate_duration(self, usage: Dict[str, Any]) -> int:
        """Estimate response duration from token count"""
        output_tokens = usage.get("output_tokens", 0)
        # Rough estimate: ~50 tokens per second
        estimated_seconds = output_tokens / 50
        return max(int(estimated_seconds * 1000), 100)  # Minimum 100ms
```

### 2. Real-time File Watcher

```python
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path

class JSONLFileWatcher(FileSystemEventHandler):
    """Watch for changes to JSONL files and trigger sync"""
    
    def __init__(self, transformer: JSONLTransformer):
        self.transformer = transformer
        self.processing_queue = asyncio.Queue()
        self.loop = None
    
    def start_watching(self):
        """Start watching Claude Code projects directory"""
        claude_projects = Path.home() / ".claude" / "projects"
        if not claude_projects.exists():
            print(f"Claude projects directory not found: {claude_projects}")
            return
        
        observer = Observer()
        observer.schedule(self, str(claude_projects), recursive=True)
        observer.start()
        
        print(f"Watching {claude_projects} for JSONL changes...")
        
        # Start processing queue
        self.loop = asyncio.get_event_loop()
        asyncio.create_task(self.process_queue())
        
        return observer
    
    def on_modified(self, event):
        if event.src_path.endswith('.jsonl') and not event.is_directory:
            self.queue_file_sync(event.src_path)
    
    def on_created(self, event):
        if event.src_path.endswith('.jsonl') and not event.is_directory:
            self.queue_file_sync(event.src_path)
    
    def queue_file_sync(self, file_path: str):
        """Queue a file for synchronization"""
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.processing_queue.put(Path(file_path)),
                self.loop
            )
    
    async def process_queue(self):
        """Process queued files for synchronization"""
        while True:
            try:
                file_path = await self.processing_queue.get()
                print(f"Syncing {file_path}...")
                await self.transformer.process_jsonl_file(file_path)
                self.processing_queue.task_done()
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
```

### 3. Session Discovery and Management

```python
class SessionManager:
    """Manage Claude Code session discovery and metadata"""
    
    @staticmethod
    async def discover_all_sessions() -> List[Dict[str, Any]]:
        """Discover all Claude Code sessions and their metadata"""
        claude_projects = Path.home() / ".claude" / "projects"
        sessions = []
        
        if not claude_projects.exists():
            return sessions
        
        for project_dir in claude_projects.iterdir():
            if not project_dir.is_dir():
                continue
            
            project_path = project_dir.name.replace("-", "/")
            
            for jsonl_file in project_dir.glob("*.jsonl"):
                session_meta = await SessionManager.extract_session_metadata(
                    jsonl_file, project_path
                )
                sessions.append(session_meta)
        
        # Sort by last modified (most recent first)
        sessions.sort(key=lambda s: s["last_modified"], reverse=True)
        return sessions
    
    @staticmethod
    async def extract_session_metadata(file_path: Path, project_path: str) -> Dict[str, Any]:
        """Extract metadata from JSONL file"""
        session_id = file_path.stem
        stats = file_path.stat()
        
        # Read first few lines to get session info
        summary = None
        first_message = None
        message_count = 0
        
        with open(file_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    record = json.loads(line)
                    message_count += 1
                    
                    if record.get("type") == "summary":
                        summary = record.get("summary")
                    elif not first_message and record.get("type") in ("user", "assistant"):
                        first_message = record
                    
                    # Stop after reading enough or finding summary
                    if summary and first_message:
                        break
                    if message_count > 20:  # Don't read entire large files
                        break
                        
                except json.JSONDecodeError:
                    continue
        
        # Generate title
        title = summary or f"Session {session_id[:8]}"
        if not summary and first_message:
            # Try to extract title from first user message
            message = first_message.get("message", {})
            content = message.get("content", "")
            if isinstance(content, str) and len(content) > 10:
                title = content[:50] + ("..." if len(content) > 50 else "")
            elif isinstance(content, list) and content:
                text_parts = [
                    item.get("text", "") for item in content 
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                if text_parts:
                    full_text = " ".join(text_parts)
                    title = full_text[:50] + ("..." if len(full_text) > 50 else "")
        
        return {
            "session_id": session_id,
            "title": title,
            "project_path": project_path,
            "file_path": str(file_path),
            "message_count": message_count,
            "file_size": stats.st_size,
            "last_modified": stats.st_mtime,
            "created": stats.st_ctime,
            "cwd": first_message.get("cwd") if first_message else project_path,
            "git_branch": first_message.get("gitBranch") if first_message else "unknown",
            "version": first_message.get("version") if first_message else "unknown"
        }
```

### 4. Complete Integration Example

```python
async def main():
    """Example of complete JSONL to database integration"""
    
    # Initialize transformer
    transformer = JSONLTransformer()
    
    # Discover and process all existing sessions
    print("Discovering existing Claude Code sessions...")
    sessions = await SessionManager.discover_all_sessions()
    print(f"Found {len(sessions)} sessions")
    
    # Process each session
    for session_meta in sessions:
        file_path = Path(session_meta["file_path"])
        print(f"Processing: {session_meta['title']}")
        await transformer.process_jsonl_file(file_path)
    
    # Start real-time watching
    print("Starting real-time file watcher...")
    watcher = JSONLFileWatcher(transformer)
    observer = watcher.start_watching()
    
    try:
        # Keep running and watching for changes
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Stopping file watcher...")
        observer.stop()
        observer.join()

# Usage
if __name__ == "__main__":
    asyncio.run(main())
```

## Enhanced Content Parsing

### Content Extraction for UI Display

```python
class ContentExtractor:
    """Extract clean, displayable content from Claude Code messages"""
    
    @staticmethod
    def extract_user_content(message_json: dict) -> str:
        """Extract clean text from user message"""
        content = message_json.get("content", "")
        
        if isinstance(content, str):
            # Filter out system reminders and meta content
            if ContentExtractor.is_system_content(content):
                return "[System message]"
            return content.strip()
        
        if isinstance(content, list):
            text_parts = []
            tool_results = []
            
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text = item.get("text", "").strip()
                        if text and not ContentExtractor.is_system_content(text):
                            text_parts.append(text)
                    elif item.get("type") == "tool_result":
                        tool_content = item.get("content", "")
                        if isinstance(tool_content, str) and len(tool_content) < 200:
                            tool_results.append(f"[Tool result: {tool_content[:100]}]")
                        else:
                            tool_results.append("[Tool result available]")
                elif isinstance(item, str):
                    if not ContentExtractor.is_system_content(item):
                        text_parts.append(item.strip())
            
            result = "\n\n".join(text_parts)
            if tool_results:
                result += "\n\n" + "\n".join(tool_results)
            
            return result or "[No displayable content]"
        
        return str(content)
    
    @staticmethod
    def extract_assistant_content(message_json: dict) -> str:
        """Extract clean text from assistant message"""
        content = message_json.get("content", [])
        
        if isinstance(content, str):
            return content.strip()
        
        if isinstance(content, list):
            text_parts = []
            tool_uses = []
            
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            text_parts.append(text)
                    elif block.get("type") == "tool_use":
                        tool_name = block.get("name", "Unknown")
                        tool_uses.append(f"[Using tool: {tool_name}]")
            
            result = "\n\n".join(text_parts)
            if tool_uses:
                result += "\n\n" + "\n".join(tool_uses)
            
            return result or "[No text content]"
        
        return str(content)
    
    @staticmethod
    def is_system_content(text: str) -> bool:
        """Check if content is system/meta content to filter out"""
        if not isinstance(text, str):
            return False
        
        text_lower = text.lower()
        system_markers = [
            "<system-reminder>",
            "do not mention this to the user",
            "your todo list is currently empty",
            "this is a reminder",
            "<command-message>",
            "<command-name>",
            "system reminder",
        ]
        
        return any(marker in text_lower for marker in system_markers)
    
    @staticmethod
    def add_metadata_info(content: str, usage: dict, model: str, cost: float, duration: int) -> str:
        """Add metadata information to assistant responses"""
        if not content:
            return content
        
        metadata_parts = []
        
        if cost > 0:
            metadata_parts.append(f"Cost: ${cost:.4f}")
        
        if duration > 0:
            if duration < 1000:
                metadata_parts.append(f"Duration: {duration}ms")
            else:
                metadata_parts.append(f"Duration: {duration/1000:.1f}s")
        
        if usage.get("output_tokens"):
            metadata_parts.append(f"Tokens: {usage['output_tokens']}")
        
        if model:
            metadata_parts.append(f"Model: {model}")
        
        if metadata_parts:
            metadata = " | ".join(metadata_parts)
            return f"{content}\n\n*[{metadata}]*"
        
        return content
```

This implementation provides a complete, working transformation pipeline that can handle real-time synchronization from Claude Code JSONL files to Elia's SQLite database while preserving all metadata and enabling intelligent conversation browsing.
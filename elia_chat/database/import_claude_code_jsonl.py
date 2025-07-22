import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from rich.console import Console
from rich.live import Live
from rich.text import Text

from elia_chat.database.database import get_session
from elia_chat.database.models import MessageDao, ChatDao


def extract_text_content(message_content: Any) -> str:
    """Handle both string and structured content formats from Claude Code JSONL"""
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
                    text_parts.append(f"🔧 **Used {tool_name}**")
                elif item.get("type") == "tool_result":
                    # Handle tool results
                    content = item.get("content", "")
                    if isinstance(content, str) and len(content) > 500:
                        content = content[:500] + "... [truncated]"
                    text_parts.append(f"📋 Tool result: {content}")
        return "\n".join(text_parts)
    
    return str(message_content)


def parse_iso_to_datetime(iso_timestamp: str) -> datetime:
    """Convert ISO timestamp to datetime object"""
    return datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))


async def discover_claude_sessions(projects_dir: Path | None = None) -> list[Path]:
    """Discover all Claude Code JSONL session files"""
    if projects_dir is None:
        projects_dir = Path.home() / ".claude" / "projects"
    
    session_files = []
    
    if not projects_dir.exists():
        return session_files
    
    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir():
            for jsonl_file in project_dir.glob("*.jsonl"):
                session_files.append(jsonl_file)
    
    return sorted(session_files, key=lambda p: p.stat().st_mtime, reverse=True)


async def import_claude_code_jsonl(file: Path) -> None:
    """Import a single Claude Code JSONL session file"""
    console = Console()
    
    def output_progress(processed_lines: int, total_lines: int, message_count: int) -> Text:
        style = "green" if processed_lines == total_lines else "yellow"
        return Text.from_markup(
            f"Processing [b]{file.name}[/]\n"
            f"Lines: [b]{processed_lines}[/] of [b]{total_lines}[/]\n"
            f"Messages: [b]{message_count}[/]",
            style=style,
        )
    
    # Read all lines to get total count
    with open(file, "r") as f:
        lines = f.readlines()
    
    total_lines = len(lines)
    message_count = 0
    processed_lines = 0
    
    # Extract session info from first few lines to create chat
    session_id = None
    summary_title = None
    first_timestamp = None
    
    # Parse lines to extract session metadata
    for line in lines[:10]:  # Check first 10 lines for session info
        try:
            data = json.loads(line.strip())
            if data.get("type") == "summary":
                summary_title = data.get("summary", "Claude Code Session")
            if not session_id and data.get("sessionId"):
                session_id = data.get("sessionId")
            if not first_timestamp and data.get("timestamp"):
                first_timestamp = parse_iso_to_datetime(data.get("timestamp"))
        except (json.JSONDecodeError, KeyError):
            continue
    
    if not session_id:
        console.print(f"[red]Could not find session ID in {file.name}")
        return
    
    with Live(output_progress(0, total_lines, message_count)) as live:
        async with get_session() as session:
            # Create chat record
            chat = ChatDao(
                title=summary_title or f"Claude Code Session ({session_id[:8]})",
                model="claude-sonnet-4",  # Default model
                started_at=first_timestamp or datetime.now(),
            )
            session.add(chat)
            await session.commit()  # Get chat.id
            
            # Process all messages
            message_map = {}  # uuid -> MessageDao for threading
            
            for line in lines:
                processed_lines += 1
                
                try:
                    data = json.loads(line.strip())
                except json.JSONDecodeError:
                    live.update(output_progress(processed_lines, total_lines, message_count))
                    continue
                
                # Skip non-message entries
                if data.get("type") not in ["user", "assistant"]:
                    live.update(output_progress(processed_lines, total_lines, message_count))
                    continue
                
                # Extract message info
                message_data = data.get("message", {})
                role = message_data.get("role", data.get("type", "user"))
                content = extract_text_content(message_data.get("content", ""))
                timestamp = parse_iso_to_datetime(data.get("timestamp", datetime.now().isoformat()))
                
                # Extract model info
                model = None
                if role == "assistant":
                    model = message_data.get("model", "claude-sonnet-4")
                    # Update chat model if we find a specific one
                    if model and "claude" in model.lower():
                        chat.model = model
                
                # Find parent message
                parent_id = None
                parent_uuid = data.get("parentUuid")
                if parent_uuid and parent_uuid in message_map:
                    parent_id = message_map[parent_uuid].id
                
                # Create message
                message = MessageDao(
                    chat_id=chat.id,
                    role=role,
                    content=content,
                    timestamp=timestamp,
                    model=model,
                    parent_id=parent_id,
                    meta={
                        "uuid": data.get("uuid"),
                        "sessionId": data.get("sessionId"),
                        "cwd": data.get("cwd"),
                        "gitBranch": data.get("gitBranch"),
                        "version": data.get("version"),
                        "usage": message_data.get("usage", {}),
                        "requestId": data.get("requestId"),
                    }
                )
                
                session.add(message)
                await session.commit()  # Get message.id for threading
                
                # Store for threading
                if data.get("uuid"):
                    message_map[data["uuid"]] = message
                
                message_count += 1
                live.update(output_progress(processed_lines, total_lines, message_count))
            
            # Final commit
            await session.commit()


async def import_all_claude_code_sessions(projects_dir: Path | None = None) -> None:
    """Import all Claude Code JSONL session files"""
    console = Console()
    
    session_files = await discover_claude_sessions(projects_dir)
    
    if not session_files:
        dir_path = projects_dir or Path.home() / ".claude" / "projects"
        console.print(f"[yellow]No Claude Code session files found in {dir_path}")
        return
    
    console.print(f"[green]Found {len(session_files)} Claude Code session files")
    
    for i, file in enumerate(session_files, 1):
        console.print(f"\n[blue]Processing session {i}/{len(session_files)}: {file.name}")
        try:
            await import_claude_code_jsonl(file)
            console.print(f"[green]✓ Successfully imported {file.name}")
        except Exception as e:
            console.print(f"[red]✗ Failed to import {file.name}: {e}")


if __name__ == "__main__":
    import asyncio
    
    asyncio.run(import_all_claude_code_sessions())
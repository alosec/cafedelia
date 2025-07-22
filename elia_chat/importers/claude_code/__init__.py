"""Claude Code session import orchestration"""

from pathlib import Path
from typing import List

from .services import (
    JsonlReader,
    MessageTransformer,
    DatabaseWriter,
    FileScanner,
    ProgressTracker,
)


class ClaudeCodeImporter:
    """Main orchestrator for Claude Code session imports"""
    
    def __init__(self, projects_dir: Path | None = None):
        self.file_scanner = FileScanner(projects_dir)
        self.progress_tracker = ProgressTracker()
        
    async def import_single_session(self, file: Path) -> None:
        """Import a single Claude Code JSONL session file"""
        if not self.file_scanner.validate_file(file):
            raise ValueError(f"Invalid file: {file}")
        
        # Initialize services
        reader = JsonlReader(file)
        transformer = MessageTransformer()
        db_writer = DatabaseWriter()
        
        # Read and parse file
        lines = reader.read_lines()
        total_lines = len(lines)
        message_count = 0
        processed_lines = 0
        
        # Extract session metadata
        metadata = reader.get_session_metadata(lines)
        
        if not metadata["session_id"]:
            raise ValueError(f"Could not find session ID in {file.name}")
        
        # Create progress display
        initial_display = self.progress_tracker.create_file_progress_display(
            file, 0, total_lines, message_count
        )
        
        with self.progress_tracker.create_live_context(initial_display) as live:
            # Create chat record
            first_timestamp = None
            if metadata["first_timestamp"]:
                first_timestamp = transformer.parse_iso_to_datetime(metadata["first_timestamp"])
            
            chat = await db_writer.create_chat(
                metadata["session_id"],
                metadata["summary_title"],
                first_timestamp
            )
            
            # Process messages
            for data in reader.parse_lines(lines):
                processed_lines += 1
                
                # Skip non-message entries
                if data.get("type") not in ["user", "assistant"]:
                    live.update(self.progress_tracker.create_file_progress_display(
                        file, processed_lines, total_lines, message_count
                    ))
                    continue
                
                # Transform and create message
                message_data = transformer.extract_message_data(data)
                await db_writer.create_message(chat, message_data)
                
                message_count += 1
                live.update(self.progress_tracker.create_file_progress_display(
                    file, processed_lines, total_lines, message_count
                ))
            
            # Finalize
            await db_writer.finalize_session()
    
    async def discover_sessions(self) -> List[Path]:
        """Discover all available Claude Code session files"""
        return await self.file_scanner.discover_session_files()
    
    async def import_all_sessions(self, projects_dir: Path | None = None) -> None:
        """Import all Claude Code JSONL session files"""
        if projects_dir:
            self.file_scanner.set_projects_directory(projects_dir)
        
        session_files = await self.discover_sessions()
        
        if not session_files:
            self.progress_tracker.print_no_files_found(self.file_scanner.get_projects_directory())
            return
        
        self.progress_tracker.print_discovery_summary(len(session_files))
        
        for i, file in enumerate(session_files, 1):
            self.progress_tracker.print_session_start(i, len(session_files), file)
            try:
                await self.import_single_session(file)
                self.progress_tracker.print_session_success(file)
            except Exception as e:
                self.progress_tracker.print_session_error(file, e)


# Public API functions for backward compatibility
async def import_claude_code_jsonl(file: Path) -> None:
    """Import a single Claude Code JSONL session file"""
    importer = ClaudeCodeImporter()
    await importer.import_single_session(file)


async def import_all_claude_code_sessions(projects_dir: Path | None = None) -> None:
    """Import all Claude Code JSONL session files"""
    importer = ClaudeCodeImporter(projects_dir)
    await importer.import_all_sessions()


async def discover_claude_sessions(projects_dir: Path | None = None) -> List[Path]:
    """Discover all Claude Code JSONL session files"""
    importer = ClaudeCodeImporter(projects_dir)
    return await importer.discover_sessions()


__all__ = [
    "ClaudeCodeImporter",
    "import_claude_code_jsonl",
    "import_all_claude_code_sessions", 
    "discover_claude_sessions",
]
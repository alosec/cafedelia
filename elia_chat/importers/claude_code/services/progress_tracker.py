"""Progress display and user feedback for Claude Code imports"""

from pathlib import Path
from rich.console import Console
from rich.live import Live
from rich.text import Text


class ProgressTracker:
    """Handles progress display and user feedback during imports"""
    
    def __init__(self):
        self.console = Console()
    
    def create_file_progress_display(
        self, 
        file: Path, 
        processed_lines: int, 
        total_lines: int, 
        message_count: int
    ) -> Text:
        """Create progress display for a single file import"""
        style = "green" if processed_lines == total_lines else "yellow"
        return Text.from_markup(
            f"Processing [b]{file.name}[/]\n"
            f"Lines: [b]{processed_lines}[/] of [b]{total_lines}[/]\n"
            f"Messages: [b]{message_count}[/]",
            style=style,
        )
    
    def print_session_start(self, session_num: int, total_sessions: int, file: Path) -> None:
        """Print start message for a session import"""
        self.console.print(f"\n[blue]Processing session {session_num}/{total_sessions}: {file.name}")
    
    def print_session_success(self, file: Path) -> None:
        """Print success message for a session import"""
        self.console.print(f"[green]✓ Successfully imported {file.name}")
    
    def print_session_error(self, file: Path, error: Exception) -> None:
        """Print error message for a session import"""
        self.console.print(f"[red]✗ Failed to import {file.name}: {error}")
    
    def print_no_files_found(self, directory: Path) -> None:
        """Print message when no session files are found"""
        self.console.print(f"[yellow]No Claude Code session files found in {directory}")
    
    def print_discovery_summary(self, file_count: int) -> None:
        """Print summary of discovered files"""
        self.console.print(f"[green]Found {file_count} Claude Code session files")
    
    def print_import_start(self, directory: Path) -> None:
        """Print start message for import process"""
        self.console.print(f"[blue]Importing Claude Code sessions from: {directory}")
    
    def print_import_complete(self, directory: Path) -> None:
        """Print completion message for import process"""
        self.console.print(f"[green]Claude Code sessions imported from {str(directory)!r}")
    
    def create_live_context(self, initial_display: Text) -> Live:
        """Create a Live context for real-time progress updates"""
        return Live(initial_display)
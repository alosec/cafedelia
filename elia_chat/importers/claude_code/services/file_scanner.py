"""File discovery and enumeration for Claude Code sessions"""

from pathlib import Path
from typing import List


class FileScanner:
    """Handles discovery of Claude Code JSONL session files"""
    
    def __init__(self, projects_dir: Path | None = None):
        self.projects_dir = projects_dir or Path.home() / ".claude" / "projects"
    
    async def discover_session_files(self) -> List[Path]:
        """Discover all Claude Code JSONL session files"""
        session_files = []
        
        if not self.projects_dir.exists():
            return session_files
        
        for project_dir in self.projects_dir.iterdir():
            if project_dir.is_dir():
                for jsonl_file in project_dir.glob("*.jsonl"):
                    session_files.append(jsonl_file)
        
        # Sort by modification time, newest first
        return sorted(session_files, key=lambda p: p.stat().st_mtime, reverse=True)
    
    def validate_file(self, file_path: Path) -> bool:
        """Validate that a file exists and is readable"""
        return file_path.exists() and file_path.is_file() and file_path.suffix == ".jsonl"
    
    def get_projects_directory(self) -> Path:
        """Get the projects directory path"""
        return self.projects_dir
    
    def set_projects_directory(self, path: Path) -> None:
        """Set a custom projects directory path"""
        self.projects_dir = path
#!/usr/bin/env python3
"""
Test the SessionLogViewer widget functionality.
"""

import asyncio
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Horizontal

from elia_chat.widgets.session_log_viewer import SessionLogViewer


class LogViewerTestApp(App):
    """Test app for the SessionLogViewer."""
    
    def compose(self) -> ComposeResult:
        yield SessionLogViewer()
    
    async def on_mount(self) -> None:
        """Start tailing a test session when the app starts."""
        # Find a real session ID from the Claude Code projects
        projects_dir = Path.home() / ".claude" / "projects" / "-home-alex-code-cafedelia"
        
        if projects_dir.exists():
            # Get the first JSONL file as a test
            jsonl_files = list(projects_dir.glob("*.jsonl"))
            if jsonl_files:
                # Extract session ID from filename
                session_id = jsonl_files[0].stem
                
                # Set the session ID to start tailing
                log_viewer = self.query_one(SessionLogViewer)
                log_viewer.session_id = session_id
                
                print(f"🧪 Testing log viewer with session: {session_id}")
                print(f"📁 JSONL file: {jsonl_files[0]}")
                print("Press Ctrl+C to exit")
            else:
                print("❌ No JSONL files found in Claude Code projects")
        else:
            print("❌ Claude Code projects directory not found")


if __name__ == "__main__":
    app = LogViewerTestApp()
    app.run()
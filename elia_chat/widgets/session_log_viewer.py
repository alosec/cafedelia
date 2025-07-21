"""
Session Log Viewer widget for real-time JSONL tailing.

Shows raw Claude Code JSON responses alongside the formatted chat interface,
providing detailed debugging visibility into the streaming protocol.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import TextArea, Static

logger = logging.getLogger(__name__)


class SessionLogViewer(Widget):
    """Real-time JSONL log viewer for Claude Code sessions."""
    
    session_id: reactive[Optional[str]] = reactive(None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._log_file_path: Optional[Path] = None
        self._tail_task: Optional[asyncio.Task] = None
        self._is_tailing = False
        self._pending_content: list[str] = []  # Queue for content before mount
        
    def compose(self) -> ComposeResult:
        """Compose the log viewer UI."""
        with Vertical():
            yield Static("📄 Session Logs", id="log-header")
            yield TextArea(
                read_only=True,
                language="json",
                theme="monokai",
                id="log-content",
                classes="session-logs"
            )
    
    def watch_session_id(self, session_id: Optional[str]) -> None:
        """React to session ID changes."""
        logger.info(f"SessionLogViewer: watch_session_id called with: {session_id}")
        if session_id:
            self._start_tailing(session_id)
        else:
            self._stop_tailing()
    
    def _start_tailing(self, session_id: str) -> None:
        """Start tailing the JSONL file for the given session."""
        try:
            logger.info(f"_start_tailing called for session: {session_id}")
            
            # Determine the JSONL file path based on current project
            project_path = Path.cwd()
            project_name = str(project_path).replace('/', '-')
            # Add leading dash as Claude Code uses it in directory names
            if not project_name.startswith('-'):
                project_name = '-' + project_name
            
            jsonl_path = Path.home() / ".claude" / "projects" / project_name / f"{session_id}.jsonl"
            
            # Enhanced debugging
            logger.info(f"Looking for JSONL file: {jsonl_path}")
            logger.info(f"Project path: {project_path}")
            logger.info(f"Project name: {project_name}")
            logger.info(f"Session ID: {session_id}")
            
            if not jsonl_path.exists():
                # Try to find the file in any project directory
                claude_projects = Path.home() / ".claude" / "projects"
                logger.info(f"Searching for {session_id}.jsonl in {claude_projects}")
                found_files = list(claude_projects.glob(f"*/{session_id}.jsonl"))
                logger.info(f"Found files: {found_files}")
                
                if found_files:
                    jsonl_path = found_files[0]
                    logger.info(f"Found JSONL file in alternative location: {jsonl_path}")
                    self._show_status(f"📡 Found: {jsonl_path.parent.name}/{jsonl_path.name}")
                else:
                    logger.warning(f"JSONL file not found anywhere: {jsonl_path}")
                    self._show_status(f"❌ Log file not found for session {session_id[:8]}...")
                    return
            else:
                logger.info(f"Found JSONL file at expected location: {jsonl_path}")
                self._show_status(f"📡 Tailing: {jsonl_path.name}")
                
            self._log_file_path = jsonl_path
            logger.info(f"Set _log_file_path to: {self._log_file_path}")
            
            # Stop any existing tailing task
            if self._tail_task:
                logger.info("Cancelling existing tail task")
                self._tail_task.cancel()
                
            # Start the tailing task
            logger.info("Creating new tail task")
            self._tail_task = asyncio.create_task(self._tail_file())
            logger.info(f"Created tail task: {self._tail_task}")
            
        except Exception as e:
            logger.error(f"Error starting log tail for session {session_id}: {e}", exc_info=True)
            self._show_status(f"❌ Error: {e}")
    
    def _stop_tailing(self) -> None:
        """Stop tailing the current file."""
        if self._tail_task:
            self._tail_task.cancel()
            self._tail_task = None
        self._is_tailing = False
        self._show_status("⏸️ No active session")
    
    async def _tail_file(self) -> None:
        """Tail the JSONL file and update the text area."""
        logger.info(f"_tail_file started with path: {self._log_file_path}")
        
        if not self._log_file_path:
            logger.warning("_tail_file: No log file path set")
            return
            
        try:
            self._is_tailing = True
            logger.info(f"_tail_file: Set _is_tailing to True")
            
            # Read existing content first
            if self._log_file_path.exists():
                logger.info(f"_tail_file: File exists, reading content")
                file_size = self._log_file_path.stat().st_size
                logger.info(f"_tail_file: File size: {file_size} bytes")
                
                # For large files, only read the last portion
                max_initial_bytes = 50000  # 50KB initial load
                
                with open(self._log_file_path, 'r', encoding='utf-8') as f:
                    if file_size > max_initial_bytes:
                        # Seek to near the end for large files
                        f.seek(max(0, file_size - max_initial_bytes))
                        # Read to end of current line to avoid partial JSON
                        f.readline()
                        existing_content = f"[...truncated {file_size - max_initial_bytes} bytes...]\n\n" + f.read()
                    else:
                        existing_content = f.read()
                    
                    logger.info(f"_tail_file: Read {len(existing_content)} characters")
                    
                    if existing_content.strip():
                        logger.info(f"_tail_file: Calling _append_content with content")
                        self._append_content(existing_content)
                    else:
                        logger.warning(f"_tail_file: Content is empty or whitespace only")
            else:
                logger.warning(f"_tail_file: File does not exist: {self._log_file_path}")
            
            # Start tailing new content
            last_size = self._log_file_path.stat().st_size if self._log_file_path.exists() else 0
            logger.info(f"_tail_file: Starting tail loop with last_size: {last_size}")
            
            while self._is_tailing:
                try:
                    current_size = self._log_file_path.stat().st_size
                    
                    if current_size > last_size:
                        logger.info(f"_tail_file: New content detected, size changed from {last_size} to {current_size}")
                        # New content available
                        with open(self._log_file_path, 'r', encoding='utf-8') as f:
                            f.seek(last_size)
                            new_content = f.read()
                            if new_content.strip():
                                logger.info(f"_tail_file: Appending {len(new_content)} new characters")
                                self._append_content(new_content)
                        last_size = current_size
                    
                    await asyncio.sleep(0.1)  # Check every 100ms
                    
                except FileNotFoundError:
                    logger.warning(f"_tail_file: File not found during tailing, waiting...")
                    # File might not exist yet, wait and retry
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error tailing file: {e}", exc_info=True)
                    break
                    
        except asyncio.CancelledError:
            logger.info("Log tailing cancelled")
        except Exception as e:
            logger.error(f"Error in tail_file: {e}", exc_info=True)
            self._show_status(f"❌ Tailing error: {e}")
        finally:
            self._is_tailing = False
            logger.info("_tail_file: Set _is_tailing to False")
    
    def _append_content(self, content: str) -> None:
        """Append new content to the log viewer with JSON formatting."""
        logger.info(f"_append_content called with {len(content)} characters")
        
        # Check if widget is mounted first
        if not self.is_mounted:
            logger.info("_append_content: Widget not mounted yet, queuing content")
            self._pending_content.append(content)
            return
        
        try:
            log_area = self.query_one("#log-content", TextArea)
            logger.info(f"_append_content: Found TextArea widget")
        except Exception as e:
            logger.error(f"_append_content: Failed to find TextArea widget: {e}")
            self._pending_content.append(content)  # Queue for later
            return
        
        # Parse and format each JSON line
        formatted_lines = []
        lines = content.strip().split('\n')
        logger.info(f"_append_content: Processing {len(lines)} lines")
        
        for i, line in enumerate(lines):
            if line.strip():
                try:
                    # Parse JSON and reformat it with indentation
                    json_obj = json.loads(line)
                    formatted_json = json.dumps(json_obj, indent=2, ensure_ascii=False)
                    formatted_lines.append(formatted_json)
                    formatted_lines.append("-" * 40)  # Separator
                    logger.debug(f"_append_content: Formatted line {i} as JSON")
                except json.JSONDecodeError as e:
                    # If not valid JSON, show raw line
                    formatted_lines.append(f"[RAW] {line}")
                    formatted_lines.append("-" * 40)
                    logger.debug(f"_append_content: Line {i} is not valid JSON: {e}")
        
        if formatted_lines:
            new_text = '\n'.join(formatted_lines)
            logger.info(f"_append_content: Formatted content length: {len(new_text)}")
            
            # Append to existing content
            current_text = log_area.text
            logger.info(f"_append_content: Current TextArea text length: {len(current_text)}")
            
            if current_text:
                log_area.text = current_text + '\n\n' + new_text
            else:
                log_area.text = new_text
            
            logger.info(f"_append_content: Set TextArea text to {len(log_area.text)} characters")
            
            # Auto-scroll to bottom
            log_area.scroll_end()
            logger.info(f"_append_content: Scrolled to end")
        else:
            logger.warning(f"_append_content: No formatted lines generated")
    
    def _show_status(self, message: str) -> None:
        """Show status message in the header."""
        try:
            header = self.query_one("#log-header", Static)
            header.update(message)
        except:
            pass  # Ignore if not mounted yet
    
    async def on_mount(self) -> None:
        """Process pending content after widget is mounted."""
        logger.info(f"SessionLogViewer mounted, processing {len(self._pending_content)} pending content items")
        
        # Process any pending content
        if self._pending_content:
            for content in self._pending_content:
                self._append_content(content)
            self._pending_content.clear()
            
        # Force a refresh of the TextArea
        try:
            log_area = self.query_one("#log-content", TextArea)
            log_area.refresh()
        except Exception as e:
            logger.error(f"Failed to refresh TextArea: {e}")
    
    async def on_unmount(self) -> None:
        """Clean up when the widget is unmounted."""
        self._stop_tailing()
    
    def clear_logs(self) -> None:
        """Clear the log content."""
        try:
            log_area = self.query_one("#log-content", TextArea)
            log_area.text = ""
        except:
            pass
    
    def save_logs(self, file_path: str) -> bool:
        """Save current log content to a file."""
        try:
            log_area = self.query_one("#log-content", TextArea)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(log_area.text)
            return True
        except Exception as e:
            logger.error(f"Error saving logs: {e}")
            return False
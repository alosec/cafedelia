"""
System status panel for displaying database operations and sync status.
Shows real-time updates of message persistence, sync operations, and system events.
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING, Deque

from textual import log
from textual.app import ComposeResult
from textual.containers import Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, Label, Button

if TYPE_CHECKING:
    from sync.session_state_manager import StateEvent


class SystemStatusPanel(Widget):
    """
    Bottom panel showing system operations and database sync status.
    Displays real-time logs of message persistence, sync events, and errors.
    """
    
    DEFAULT_CSS = """
    SystemStatusPanel {
        dock: bottom;
        height: 12;
        background: $surface;
        border-top: solid $primary;
        display: none;
    }
    
    SystemStatusPanel.visible {
        display: block;
    }
    
    #status-header {
        height: 3;
        padding: 0 2;
        background: $boost;
        color: $text;
    }
    
    #status-content {
        height: 1fr;
        overflow-y: scroll;
        padding: 0 1;
    }
    
    .status-entry {
        padding: 0 1;
        margin: 0 0 1 0;
    }
    
    .status-entry.info {
        color: $text-muted;
    }
    
    .status-entry.success {
        color: $success;
    }
    
    .status-entry.warning {
        color: $warning;
    }
    
    .status-entry.error {
        color: $error;
    }
    
    .status-timestamp {
        color: $text-disabled;
        text-style: dim;
    }
    """
    
    # Current sync status
    sync_status = reactive("Idle")
    active_sessions = reactive(0)
    messages_synced = reactive(0)
    
    def __init__(self) -> None:
        super().__init__()
        self.log_entries: Deque[tuple[datetime, str, str]] = deque(maxlen=100)
        self._update_task: asyncio.Task | None = None
        
    def compose(self) -> ComposeResult:
        """Compose the status panel layout."""
        with Vertical(id="status-header"):
            yield Label(
                f"System Status: {self.sync_status} | Sessions: {self.active_sessions} | Messages: {self.messages_synced}",
                id="status-summary"
            )
            yield Static("Press F4 to hide", classes="text-muted")
            
        with ScrollableContainer(id="status-content"):
            # Log entries will be added here dynamically
            pass
    
    def on_mount(self) -> None:
        """Start monitoring system events when mounted."""
        self._register_event_handlers()
        self._update_task = asyncio.create_task(self._periodic_update())
        
    def on_unmount(self) -> None:
        """Clean up event handlers when unmounted."""
        self._unregister_event_handlers()
        if self._update_task:
            self._update_task.cancel()
    
    def _register_event_handlers(self) -> None:
        """Register handlers for session state manager events."""
        try:
            from sync.session_state_manager import session_state_manager
            
            session_state_manager.add_event_handler('message_added', self._on_message_added)
            session_state_manager.add_event_handler('parity_issue', self._on_parity_issue)
            session_state_manager.add_event_handler('sync_complete', self._on_sync_complete)
            session_state_manager.add_event_handler('error', self._on_error)
            
            log.debug("Registered system status panel event handlers")
        except ImportError:
            log.warning("Could not import session_state_manager for status panel")
    
    def _unregister_event_handlers(self) -> None:
        """Unregister event handlers."""
        try:
            from sync.session_state_manager import session_state_manager
            
            session_state_manager.remove_event_handler('message_added', self._on_message_added)
            session_state_manager.remove_event_handler('parity_issue', self._on_parity_issue)
            session_state_manager.remove_event_handler('sync_complete', self._on_sync_complete)
            session_state_manager.remove_event_handler('error', self._on_error)
        except ImportError:
            pass
    
    def _on_message_added(self, event: StateEvent) -> None:
        """Handle message added events."""
        message_type = event.metadata.get('message_type', 'unknown')
        content_length = event.metadata.get('content_length', 0)
        self.add_log_entry(
            f"Message registered: {message_type} ({content_length} chars)",
            "success"
        )
        self.messages_synced += 1
        
    def _on_parity_issue(self, event: StateEvent) -> None:
        """Handle parity issue events."""
        diff = event.data.get('difference', 0)
        self.add_log_entry(
            f"Parity issue detected: {diff} message(s) out of sync",
            "warning"
        )
        
    def _on_sync_complete(self, event: StateEvent) -> None:
        """Handle sync completion events."""
        correction = event.data.get('correction_applied', False)
        msg = "Sync completed" + (" with corrections" if correction else "")
        self.add_log_entry(msg, "success")
        
    def _on_error(self, event: StateEvent) -> None:
        """Handle error events."""
        error = event.data.get('error', 'Unknown error')
        context = event.data.get('context', '')
        self.add_log_entry(
            f"Error in {context}: {error}",
            "error"
        )
    
    def add_log_entry(self, message: str, level: str = "info") -> None:
        """Add a new log entry to the panel."""
        timestamp = datetime.now()
        self.log_entries.append((timestamp, message, level))
        
        # Update UI
        self.app.call_from_thread(self._refresh_log_display)
    
    def _refresh_log_display(self) -> None:
        """Refresh the log display with current entries."""
        content = self.query_one("#status-content", ScrollableContainer)
        
        # Clear existing entries
        content.remove_children()
        
        # Add log entries
        for timestamp, message, level in self.log_entries:
            time_str = timestamp.strftime("%H:%M:%S")
            entry = Static(
                f"[{time_str}] {message}",
                classes=f"status-entry {level}"
            )
            content.mount(entry)
        
        # Scroll to bottom
        content.scroll_end(animate=False)
        
        # Update summary
        summary = self.query_one("#status-summary", Label)
        summary.update(
            f"System Status: {self.sync_status} | Sessions: {self.active_sessions} | Messages: {self.messages_synced}"
        )
    
    async def _periodic_update(self) -> None:
        """Periodically update system statistics."""
        while True:
            try:
                await asyncio.sleep(5)  # Update every 5 seconds
                
                # Get current stats from session state manager
                try:
                    from sync.session_state_manager import session_state_manager
                    stats = await session_state_manager.get_all_session_stats()
                    
                    self.active_sessions = len(stats)
                    
                    # Determine overall sync status
                    if any(s.get('is_syncing', False) for s in stats.values()):
                        self.sync_status = "Syncing"
                    elif any(s.get('has_parity_issues', False) for s in stats.values()):
                        self.sync_status = "Parity Issues"
                    else:
                        self.sync_status = "Idle"
                    
                    self._refresh_log_display()
                    
                except ImportError:
                    pass
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in status panel update: {e}")
    
    def toggle_visibility(self) -> None:
        """Toggle the visibility of the status panel."""
        if self.has_class("visible"):
            self.remove_class("visible")
            self.add_log_entry("Status panel hidden", "info")
        else:
            self.add_class("visible")
            self.add_log_entry("Status panel shown", "info")
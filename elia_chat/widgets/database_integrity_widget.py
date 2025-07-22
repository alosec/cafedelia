"""
Database integrity check widget for startup display.

Shows database integrity issues and offers repair options in a friendly UI.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Dict, Any
from rich.table import Table
from rich.text import Text
from textual import log
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.widget import Widget
from textual.widgets import Static, Button, Label
from textual.message import Message

if TYPE_CHECKING:
    from sync.database_integrity import DatabaseIntegrityChecker


class DatabaseIntegrityWidget(Widget):
    """Widget displaying database integrity check results with repair options."""
    
    DEFAULT_CSS = """
    DatabaseIntegrityWidget {
        background: $boost;
        border: solid $primary;
        padding: 1 2;
        margin: 1 4;
        height: auto;
        max-height: 20;
    }
    
    DatabaseIntegrityWidget .integrity-title {
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    
    DatabaseIntegrityWidget .stats-table {
        margin: 1 0;
    }
    
    DatabaseIntegrityWidget .repair-buttons {
        margin-top: 1;
        height: 3;
    }
    
    DatabaseIntegrityWidget Button {
        margin: 0 1;
    }
    
    DatabaseIntegrityWidget .repair-success {
        color: $success;
        text-style: bold;
    }
    
    DatabaseIntegrityWidget .repair-progress {
        color: $text-muted;
        text-style: italic;
    }
    """
    
    BINDINGS = [
        Binding("r", "repair", "Repair Database", key_display="r"),
        Binding("escape,d", "dismiss", "Dismiss", key_display="esc"),
    ]
    
    def __init__(self, integrity_report: Dict[str, Any]) -> None:
        super().__init__()
        self.integrity_report = integrity_report
        self.is_repairing = False
        self.repair_complete = False
    
    def compose(self) -> ComposeResult:
        """Compose the integrity check UI."""
        stats = self.integrity_report['stats']
        
        with Vertical():
            # Title
            yield Static(
                "🔧 Database Integrity Check - Issues Detected!",
                classes="integrity-title"
            )
            
            # Summary message
            yield Static(self._get_summary_message())
            
            # Stats table
            yield self._create_stats_table()
            
            # Repair buttons
            with Horizontal(classes="repair-buttons"):
                yield Button("Repair Database [r]", variant="primary", id="repair-btn")
                yield Button("Dismiss [esc]", variant="default", id="dismiss-btn")
            
            # Status message area
            yield Label("", id="status-message")
    
    def _get_summary_message(self) -> str:
        """Get a friendly summary message."""
        stats = self.integrity_report['stats']
        invalid = stats['invalid_chats']
        orphaned = stats['orphaned_chats']
        
        if invalid > 0 and orphaned > 0:
            return (
                f"Hey buddy! Found {invalid} fake session entries and "
                f"{orphaned} orphaned chats in your database. Want me to clean that up?"
            )
        elif invalid > 0:
            return (
                f"Hey there! Found {invalid} entries with fake session IDs "
                f"(like 'temp_abc123'). Let's fix that!"
            )
        elif orphaned > 0:
            return (
                f"Hmm, found {orphaned} chat entries without matching session files. "
                f"Should we clean those up?"
            )
        else:
            return "Found some database inconsistencies. Let's get them sorted!"
    
    def _create_stats_table(self) -> Widget:
        """Create a table showing integrity stats."""
        stats = self.integrity_report['stats']
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="bold")
        table.add_column("Count", justify="right")
        
        table.add_row("Total Chats:", str(stats['total_chats']))
        table.add_row("[green]Valid Chats:[/green]", f"[green]{stats['valid_chats']}[/green]")
        
        if stats['invalid_chats'] > 0:
            table.add_row(
                "[red]Invalid Session IDs:[/red]", 
                f"[red]{stats['invalid_chats']}[/red]"
            )
        
        if stats['orphaned_chats'] > 0:
            table.add_row(
                "[yellow]Orphaned Chats:[/yellow]", 
                f"[yellow]{stats['orphaned_chats']}[/yellow]"
            )
        
        return Static(table, classes="stats-table")
    
    async def action_repair(self) -> None:
        """Start the repair process."""
        if self.is_repairing:
            return
        
        self.is_repairing = True
        
        # Update UI
        repair_btn = self.query_one("#repair-btn", Button)
        repair_btn.disabled = True
        repair_btn.label = "Repairing..."
        
        status = self.query_one("#status-message", Label)
        status.update("🔄 Repairing database... This may take a moment.")
        status.add_class("repair-progress")
        
        # Run repair in background
        asyncio.create_task(self._run_repair())
    
    async def _run_repair(self) -> None:
        """Run the actual repair process."""
        try:
            from sync.database_integrity import DatabaseIntegrityChecker
            
            checker = DatabaseIntegrityChecker()
            repair_report = await checker.repair_database(
                remove_invalid=True,
                remove_orphaned=True
            )
            
            # Update UI with results
            status = self.query_one("#status-message", Label)
            status.remove_class("repair-progress")
            status.add_class("repair-success")
            
            deleted_count = len(repair_report['deleted_chats'])
            if deleted_count > 0:
                status.update(
                    f"✅ Repair complete! Removed {deleted_count} invalid entries. "
                    f"Your database is now clean!"
                )
            else:
                status.update("✅ No invalid entries found. Database is already clean!")
            
            self.repair_complete = True
            
            # Update button
            repair_btn = self.query_one("#repair-btn", Button)
            repair_btn.label = "Repair Complete ✓"
            
            # Auto-dismiss after 3 seconds
            await asyncio.sleep(3)
            self.action_dismiss()
            
        except Exception as e:
            log.error(f"Database repair failed: {e}")
            status = self.query_one("#status-message", Label)
            status.update(f"❌ Repair failed: {str(e)}")
            status.add_class("error")
    
    def action_dismiss(self) -> None:
        """Dismiss the integrity check widget."""
        # Remove ourselves from parent
        self.remove()
        
        # If repair was done, refresh the history
        if self.repair_complete:
            # Post a message to trigger history refresh
            self.post_message(DatabaseRepairComplete())
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "repair-btn" and not self.is_repairing:
            self.action_repair()
        elif event.button.id == "dismiss-btn":
            self.action_dismiss()


class DatabaseRepairComplete(Message):
    """Message sent when database repair is complete."""
    pass
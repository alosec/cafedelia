"""
Widget for displaying and managing Claude Code sessions
"""

import asyncio
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Horizontal, Vertical
from textual.events import Mount
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, DataTable, Button

from bridge.session_sync import get_session_sync
from elia_chat.database.models import ClaudeSessionDao


class ClaudeSessionsWidget(Widget):
    """Widget displaying Claude Code sessions"""
    
    DEFAULT_CSS = """
    ClaudeSessionsWidget {
        background: $background 15%;
        border: solid $primary;
        height: 1fr;
        min-height: 10;
        margin: 1;
    }
    
    ClaudeSessionsWidget > Vertical {
        height: 1fr;
    }
    
    ClaudeSessionsWidget DataTable {
        height: 1fr;
    }
    
    ClaudeSessionsWidget .header {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-align: center;
    }
    
    ClaudeSessionsWidget .sync-button {
        margin: 0 1;
        width: auto;
    }
    """
    
    sessions_count = reactive(0)
    is_loading = reactive(False)
    
    def compose(self) -> ComposeResult:
        """Compose the Claude sessions widget"""
        with Vertical():
            yield Static("Claude Code Sessions", classes="header")
            with Horizontal():
                yield Button("🔄 Sync", variant="primary", classes="sync-button", id="sync-sessions")
                yield Static(f"Sessions: {self.sessions_count}", id="session-count")
            with ScrollableContainer():
                yield DataTable(id="sessions-table")
    
    async def on_mount(self) -> None:
        """Initialize the sessions table"""
        table = self.query_one("#sessions-table", DataTable)
        table.add_columns("Project", "Sessions", "Last Activity", "Status")
        await self.load_sessions()
    
    async def load_sessions(self) -> None:
        """Load Claude Code sessions from database"""
        self.is_loading = True
        
        try:
            sync = get_session_sync()
            
            # Get all sessions grouped by project
            sessions = await sync.get_local_sessions()
            
            # Group by project
            projects = {}
            for session in sessions:
                project = session.project_name
                if project not in projects:
                    projects[project] = {
                        'sessions': [],
                        'last_activity': session.last_activity
                    }
                projects[project]['sessions'].append(session)
                if session.last_activity > projects[project]['last_activity']:
                    projects[project]['last_activity'] = session.last_activity
            
            # Update table
            table = self.query_one("#sessions-table", DataTable)
            table.clear()
            
            for project_name, project_data in projects.items():
                session_count = len(project_data['sessions'])
                last_activity = project_data['last_activity'].strftime("%Y-%m-%d %H:%M")
                active_sessions = sum(1 for s in project_data['sessions'] if s.status == 'active')
                status = f"{active_sessions} active" if active_sessions > 0 else "inactive"
                
                table.add_row(project_name, str(session_count), last_activity, status)
            
            self.sessions_count = len(sessions)
            count_widget = self.query_one("#session-count", Static)
            count_widget.update(f"Sessions: {self.sessions_count}")
            
            await sync.close()
            
        except Exception as e:
            # Show error in table
            table = self.query_one("#sessions-table", DataTable)
            table.clear()
            table.add_row("Error loading sessions", str(e), "", "")
        
        finally:
            self.is_loading = False
    
    @on(Button.Pressed, "#sync-sessions")
    async def sync_sessions(self) -> None:
        """Sync sessions from backend"""
        if self.is_loading:
            return
            
        self.is_loading = True
        button = self.query_one("#sync-sessions", Button)
        button.label = "🔄 Syncing..."
        button.disabled = True
        
        try:
            sync = get_session_sync()
            result = await sync.sync_all_sessions()
            
            # Show sync result briefly
            button.label = f"✅ Synced {result['created'] + result['updated']}"
            await asyncio.sleep(1)
            
            # Reload the display
            await self.load_sessions()
            await sync.close()
            
        except Exception as e:
            button.label = f"❌ Error: {str(e)[:20]}..."
            await asyncio.sleep(2)
        
        finally:
            button.label = "🔄 Sync"
            button.disabled = False
            self.is_loading = False
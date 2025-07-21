"""
Sync Manager Screen

Full-screen interface for managing WTE pipeline server.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Footer, Header

from ..widgets.sync_manager import SyncManagerWidget
from sync.wte.simple_manager import SimpleWTEServer


class SyncManagerScreen(Screen):
    """Full-screen sync manager interface"""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("f1", "start_all", "Start All"),
        ("f2", "stop_all", "Stop All"), 
        ("f3", "restart_all", "Restart All"),
        ("r", "refresh", "Refresh"),
    ]
    
    def __init__(self, server: SimpleWTEServer, **kwargs):
        super().__init__(**kwargs)
        self.server = server
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(id="sync-screen-container"):
            yield SyncManagerWidget(self.server)
        
        yield Footer()
    
    async def action_start_all(self) -> None:
        """Start all pipelines"""
        sync_widget = self.query_one(SyncManagerWidget)
        await sync_widget.start_all_pipelines()
        
    async def action_stop_all(self) -> None:
        """Stop all pipelines"""
        sync_widget = self.query_one(SyncManagerWidget)
        await sync_widget.stop_all_pipelines()
        
    async def action_restart_all(self) -> None:
        """Restart all pipelines"""
        sync_widget = self.query_one(SyncManagerWidget)
        await sync_widget.restart_all_pipelines()
        
    def action_refresh(self) -> None:
        """Refresh the display"""
        # The widgets auto-refresh, but this could force an immediate update
        pass
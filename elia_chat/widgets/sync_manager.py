"""
Sync Manager Widget

Textual widget for managing WTE pipeline server operations.
Provides real-time monitoring and control of sync pipelines.
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Static, Label, ProgressBar
from textual.widget import Widget
from textual.reactive import reactive
from textual.timer import Timer

from sync.wte.simple_manager import SimpleWTEServer, PipelineStatus, PipelineInfo


class PipelineStatusWidget(Widget):
    """Widget displaying status of a single pipeline"""
    
    pipeline_id: reactive[str] = reactive("")
    pipeline_info: reactive[Optional[PipelineInfo]] = reactive(None)
    
    def __init__(self, pipeline_id: str, server: SimpleWTEServer, **kwargs):
        super().__init__(**kwargs)
        self.pipeline_id = pipeline_id
        self.server = server
        
    def compose(self) -> ComposeResult:
        with Container(classes="pipeline-container"):
            with Horizontal(classes="pipeline-header"):
                yield Label(f"Pipeline: {self.pipeline_id}", classes="pipeline-name")
                yield Button("Start", id=f"start-{self.pipeline_id}", classes="start-btn")
                yield Button("Stop", id=f"stop-{self.pipeline_id}", classes="stop-btn")
                yield Button("Restart", id=f"restart-{self.pipeline_id}", classes="restart-btn")
            
            with Horizontal(classes="pipeline-status"):
                yield Static("Status:", classes="status-label")
                yield Static("Unknown", id=f"status-{self.pipeline_id}", classes="status-value")
                
                yield Static("Events:", classes="events-label") 
                yield Static("0", id=f"events-{self.pipeline_id}", classes="events-value")
                
                yield Static("Errors:", classes="errors-label")
                yield Static("0", id=f"errors-{self.pipeline_id}", classes="errors-value")
            
            yield Static("", id=f"last-error-{self.pipeline_id}", classes="error-message")
    
    def on_mount(self) -> None:
        # Start periodic status updates
        self.set_interval(1.0, self.update_status)
    
    def update_status(self) -> None:
        """Update pipeline status display"""
        info = self.server.get_pipeline_status(self.pipeline_id)
        if info:
            self.pipeline_info = info
            
            # Update status
            status_widget = self.query_one(f"#status-{self.pipeline_id}", Static)
            status_widget.update(info.status.value.title())
            
            # Update events count
            events_widget = self.query_one(f"#events-{self.pipeline_id}", Static)
            events_widget.update(str(info.events_processed))
            
            # Update errors count
            errors_widget = self.query_one(f"#errors-{self.pipeline_id}", Static)
            errors_widget.update(str(info.error_count))
            
            # Update error message
            error_widget = self.query_one(f"#last-error-{self.pipeline_id}", Static)
            error_msg = info.last_error if info.last_error else ""
            error_widget.update(f"Last Error: {error_msg}" if error_msg else "")
            
            # Update button states
            start_btn = self.query_one(f"#start-{self.pipeline_id}", Button)
            stop_btn = self.query_one(f"#stop-{self.pipeline_id}", Button)
            restart_btn = self.query_one(f"#restart-{self.pipeline_id}", Button)
            
            if info.status == PipelineStatus.RUNNING:
                start_btn.disabled = True
                stop_btn.disabled = False
                restart_btn.disabled = False
            elif info.status == PipelineStatus.STOPPED:
                start_btn.disabled = False
                stop_btn.disabled = True
                restart_btn.disabled = True
            else:
                start_btn.disabled = True
                stop_btn.disabled = True
                restart_btn.disabled = True
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        button_id = event.button.id
        
        if button_id == f"start-{self.pipeline_id}":
            await self.server.start_pipeline(self.pipeline_id)
        elif button_id == f"stop-{self.pipeline_id}":
            await self.server.stop_pipeline(self.pipeline_id)
        elif button_id == f"restart-{self.pipeline_id}":
            await self.server.stop_pipeline(self.pipeline_id)
            await asyncio.sleep(0.5)  # Brief pause
            await self.server.start_pipeline(self.pipeline_id)


class SyncManagerWidget(Widget):
    """Main sync manager widget"""
    
    def __init__(self, server: SimpleWTEServer, **kwargs):
        super().__init__(**kwargs)
        self.server = server
    
    def compose(self) -> ComposeResult:
        with Container(id="sync-manager"):
            yield Static("WTE Pipeline Manager", classes="title")
            
            with Horizontal(classes="server-controls"):
                yield Button("Start All", id="start-all", classes="server-btn")
                yield Button("Stop All", id="stop-all", classes="server-btn")
                yield Button("Restart All", id="restart-all", classes="server-btn")
                yield Static("Server: ", classes="server-status-label")
                yield Static("Unknown", id="server-status", classes="server-status-value")
            
            with Vertical(classes="pipelines-container"):
                # Add pipeline status widgets for each pipeline
                for pipeline_id in ["session_registration", "jsonl_sync", "live_chat"]:
                    yield PipelineStatusWidget(pipeline_id, self.server, classes="pipeline-widget")
            
            # System information
            with Container(classes="system-info"):
                yield Static("System Information", classes="section-title")
                yield Static("", id="system-uptime", classes="system-stat")
                yield Static("", id="system-health", classes="system-stat")
                yield Static("", id="total-events", classes="system-stat")
    
    def on_mount(self) -> None:
        # Start periodic system updates
        self.set_interval(1.0, self.update_system_info)
    
    def update_system_info(self) -> None:
        """Update system information display"""
        # Server status
        server_status = self.query_one("#server-status", Static)
        status = "Running" if self.server.is_running else "Stopped"
        server_status.update(status)
        
        # Health check
        health_widget = self.query_one("#system-health", Static)
        health = "Healthy" if self.server.is_healthy() else "Unhealthy"
        health_widget.update(f"Health: {health}")
        
        # Total events processed
        total_events = sum(
            info.events_processed 
            for info in self.server.get_all_pipeline_status().values()
        )
        events_widget = self.query_one("#total-events", Static)
        events_widget.update(f"Total Events Processed: {total_events}")
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle server control buttons"""
        button_id = event.button.id
        
        if button_id == "start-all":
            await self.start_all_pipelines()
        elif button_id == "stop-all":
            await self.stop_all_pipelines()
        elif button_id == "restart-all":
            await self.restart_all_pipelines()
    
    async def start_all_pipelines(self) -> None:
        """Start all pipelines"""
        pipelines = self.server.get_all_pipeline_status()
        tasks = []
        
        for pipeline_id in pipelines.keys():
            tasks.append(self.server.start_pipeline(pipeline_id))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all_pipelines(self) -> None:
        """Stop all pipelines"""
        pipelines = self.server.get_all_pipeline_status()
        tasks = []
        
        for pipeline_id in pipelines.keys():
            tasks.append(self.server.stop_pipeline(pipeline_id))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def restart_all_pipelines(self) -> None:
        """Restart all pipelines"""
        await self.stop_all_pipelines()
        await asyncio.sleep(1.0)  # Brief pause
        await self.start_all_pipelines()


class SyncManagerModal(Container):
    """Modal screen for sync manager"""
    
    def __init__(self, server: SimpleWTEServer, **kwargs):
        super().__init__(**kwargs)
        self.server = server
    
    def compose(self) -> ComposeResult:
        with Container(classes="sync-modal"):
            yield SyncManagerWidget(self.server)
            with Horizontal(classes="modal-buttons"):
                yield Button("Close", id="close-modal", variant="primary")
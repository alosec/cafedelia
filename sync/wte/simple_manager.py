"""
Simplified WTE Manager

A simplified version of the WTE architecture that works with existing cafedelia infrastructure.
Focuses on the core GUI and server management without complex dependencies.
"""

import asyncio
import logging
from typing import Dict, Optional, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


class PipelineStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting" 
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class PipelineInfo:
    """Simplified pipeline information"""
    name: str
    status: PipelineStatus = PipelineStatus.STOPPED
    task: Optional[asyncio.Task] = None
    start_time: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    events_processed: int = 0


class SimplePipeline:
    """Simplified pipeline for demonstration"""
    
    def __init__(self, name: str):
        self.name = name
        self.running = False
        self.events_processed = 0
        
    async def run(self):
        """Simple pipeline runner"""
        self.running = True
        logger.info(f"Starting pipeline: {self.name}")
        
        try:
            while self.running:
                # Simulate processing events
                await asyncio.sleep(2)
                self.events_processed += 1
                logger.info(f"Pipeline {self.name} processed event #{self.events_processed}")
                
        except asyncio.CancelledError:
            logger.info(f"Pipeline {self.name} cancelled")
            self.running = False
            raise
        except Exception as e:
            logger.error(f"Pipeline {self.name} error: {e}")
            self.running = False
            raise
    
    def stop(self):
        """Stop the pipeline"""
        self.running = False


class SimpleWTEServer:
    """Simplified WTE server for GUI demonstration"""
    
    def __init__(self):
        self.pipelines: Dict[str, PipelineInfo] = {}
        self.is_running = False
        self.pipeline_instances: Dict[str, SimplePipeline] = {}
        
        # Initialize pipeline definitions
        self._init_pipelines()
    
    def _init_pipelines(self):
        """Initialize available pipelines"""
        pipeline_names = [
            ("session_registration", "Session Registration"),
            ("jsonl_sync", "JSONL Sync"),
            ("live_chat", "Live Chat Integration")
        ]
        
        for pipeline_id, display_name in pipeline_names:
            self.pipelines[pipeline_id] = PipelineInfo(name=display_name)
            self.pipeline_instances[pipeline_id] = SimplePipeline(display_name)
    
    async def start_server(self):
        """Start the server"""
        logger.info("Starting Simple WTE Server")
        self.is_running = True
        
        # Auto-start session registration pipeline
        await self.start_pipeline("session_registration")
        
        logger.info("Simple WTE Server started successfully")
    
    async def stop_server(self):
        """Stop the server"""
        logger.info("Stopping Simple WTE Server")
        self.is_running = False
        
        # Stop all pipelines
        for pipeline_id in list(self.pipelines.keys()):
            await self.stop_pipeline(pipeline_id)
        
        logger.info("Simple WTE Server stopped")
    
    async def start_pipeline(self, pipeline_id: str) -> bool:
        """Start a specific pipeline"""
        if pipeline_id not in self.pipelines:
            logger.error(f"Unknown pipeline: {pipeline_id}")
            return False
        
        info = self.pipelines[pipeline_id]
        
        if info.status in [PipelineStatus.RUNNING, PipelineStatus.STARTING]:
            logger.warning(f"Pipeline {pipeline_id} already running")
            return True
        
        try:
            info.status = PipelineStatus.STARTING
            logger.info(f"Starting pipeline: {info.name}")
            
            # Start pipeline task
            pipeline_instance = self.pipeline_instances[pipeline_id]
            info.task = asyncio.create_task(pipeline_instance.run())
            
            info.status = PipelineStatus.RUNNING
            info.start_time = datetime.now()
            info.error_count = 0
            info.last_error = None
            
            logger.info(f"Pipeline {info.name} started successfully")
            return True
            
        except Exception as e:
            info.status = PipelineStatus.ERROR
            info.last_error = str(e)
            logger.error(f"Failed to start pipeline {info.name}: {e}")
            return False
    
    async def stop_pipeline(self, pipeline_id: str) -> bool:
        """Stop a specific pipeline"""
        if pipeline_id not in self.pipelines:
            logger.error(f"Unknown pipeline: {pipeline_id}")
            return False
        
        info = self.pipelines[pipeline_id]
        
        if info.status == PipelineStatus.STOPPED:
            logger.info(f"Pipeline {pipeline_id} already stopped")
            return True
        
        try:
            info.status = PipelineStatus.STOPPING
            logger.info(f"Stopping pipeline: {info.name}")
            
            # Stop pipeline instance
            pipeline_instance = self.pipeline_instances[pipeline_id]
            pipeline_instance.stop()
            
            # Cancel task
            if info.task and not info.task.done():
                info.task.cancel()
                try:
                    await info.task
                except asyncio.CancelledError:
                    pass
            
            info.status = PipelineStatus.STOPPED
            info.task = None
            info.start_time = None
            
            logger.info(f"Pipeline {info.name} stopped successfully")
            return True
            
        except Exception as e:
            info.status = PipelineStatus.ERROR
            info.last_error = str(e)
            logger.error(f"Failed to stop pipeline {info.name}: {e}")
            return False
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[PipelineInfo]:
        """Get status of a specific pipeline"""
        info = self.pipelines.get(pipeline_id)
        if info and pipeline_id in self.pipeline_instances:
            # Update events processed from pipeline instance
            info.events_processed = self.pipeline_instances[pipeline_id].events_processed
        return info
    
    def get_all_pipeline_status(self) -> Dict[str, PipelineInfo]:
        """Get status of all pipelines"""
        # Update all pipeline info
        for pipeline_id, info in self.pipelines.items():
            if pipeline_id in self.pipeline_instances:
                info.events_processed = self.pipeline_instances[pipeline_id].events_processed
        
        return self.pipelines.copy()
    
    def is_healthy(self) -> bool:
        """Check if server is healthy"""
        if not self.is_running:
            return False
        
        # Check if any critical pipelines are in error state
        critical_pipelines = ['session_registration', 'jsonl_sync']
        for pipeline_id in critical_pipelines:
            info = self.pipelines.get(pipeline_id)
            if info and info.status == PipelineStatus.ERROR:
                return False
        
        return True
    
    async def wait_for_shutdown(self):
        """Wait for server shutdown"""
        while self.is_running:
            await asyncio.sleep(0.1)
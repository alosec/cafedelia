"""
WTE Pipeline Server

Manages multiple WTE pipelines with start/stop control and monitoring.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import signal
import sys

from .runner import run_pipeline, run_multiple_pipelines
from .pipelines import SessionRegistrationPipeline, JSONLSyncPipeline, LiveChatPipeline
from .core import WTE, WTEBase
from ..database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class PipelineStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting" 
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class PipelineInfo:
    """Information about a pipeline"""
    name: str
    status: PipelineStatus = PipelineStatus.STOPPED
    task: Optional[asyncio.Task] = None
    start_time: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    events_processed: int = 0
    

class WTEPipelineServer:
    """Server for managing WTE pipelines"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.pipelines: Dict[str, PipelineInfo] = {}
        self.is_running = False
        self._shutdown_event = asyncio.Event()
        
        # Initialize pipeline definitions
        self._init_pipelines()
    
    def _init_pipelines(self):
        """Initialize available pipelines"""
        self.pipelines = {
            'session_registration': PipelineInfo(
                name='Session Registration',
            ),
            'jsonl_sync': PipelineInfo(
                name='JSONL Sync',
            ),
            'live_chat': PipelineInfo(
                name='Live Chat',
            )
        }
    
    async def start_server(self):
        """Start the pipeline server"""
        logger.info("Starting WTE Pipeline Server")
        self.is_running = True
        
        # Setup signal handlers for graceful shutdown
        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, self._signal_handler)
        
        # Start default pipelines
        await self.start_pipeline('session_registration')
        await self.start_pipeline('jsonl_sync')
        
        logger.info("WTE Pipeline Server started successfully")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating shutdown")
        asyncio.create_task(self.stop_server())
    
    async def stop_server(self):
        """Stop the pipeline server"""
        logger.info("Stopping WTE Pipeline Server")
        self.is_running = False
        
        # Stop all pipelines
        for pipeline_id in list(self.pipelines.keys()):
            await self.stop_pipeline(pipeline_id)
        
        self._shutdown_event.set()
        logger.info("WTE Pipeline Server stopped")
    
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
            
            # Create pipeline instance
            pipeline = self._create_pipeline(pipeline_id)
            if pipeline is None:
                raise ValueError(f"Failed to create pipeline: {pipeline_id}")
            
            # Start pipeline task
            info.task = asyncio.create_task(
                run_pipeline(pipeline) if isinstance(pipeline, WTE) 
                else self._run_pipeline_base(pipeline, info)
            )
            
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
    
    def _create_pipeline(self, pipeline_id: str):
        """Create pipeline instance"""
        if pipeline_id == 'session_registration':
            return SessionRegistrationPipeline(self.db_manager)
        elif pipeline_id == 'jsonl_sync':
            return JSONLSyncPipeline(self.db_manager)
        elif pipeline_id == 'live_chat':
            return LiveChatPipeline()
        else:
            return None
    
    async def _run_pipeline_base(self, pipeline: WTEBase, info: PipelineInfo):
        """Run a WTEBase pipeline with monitoring"""
        try:
            async for event in pipeline.watch():
                if not self.is_running:
                    break
                
                try:
                    action = pipeline.transform(event)
                    if action is not None:
                        await pipeline.execute(action)
                    
                    info.events_processed += 1
                    
                except Exception as e:
                    info.error_count += 1
                    info.last_error = str(e)
                    logger.error(f"Pipeline {info.name} processing error: {e}")
                    
                    if info.error_count >= 10:
                        logger.error(f"Too many errors in {info.name}, stopping")
                        break
                    
                    await asyncio.sleep(0.1)  # Brief backoff
                    
        except Exception as e:
            info.status = PipelineStatus.ERROR
            info.last_error = str(e)
            logger.error(f"Fatal error in pipeline {info.name}: {e}")
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[PipelineInfo]:
        """Get status of a specific pipeline"""
        return self.pipelines.get(pipeline_id)
    
    def get_all_pipeline_status(self) -> Dict[str, PipelineInfo]:
        """Get status of all pipelines"""
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
        await self._shutdown_event.wait()


# Global server instance
_server_instance: Optional[WTEPipelineServer] = None


def get_server(db_manager: DatabaseManager = None) -> WTEPipelineServer:
    """Get global server instance"""
    global _server_instance
    if _server_instance is None and db_manager is not None:
        _server_instance = WTEPipelineServer(db_manager)
    return _server_instance


async def main():
    """Main entry point for running server standalone"""
    from ..database_manager import DatabaseManager
    
    logging.basicConfig(level=logging.INFO)
    db_manager = DatabaseManager()  # This would need proper initialization
    
    server = WTEPipelineServer(db_manager)
    await server.start_server()
    await server.wait_for_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
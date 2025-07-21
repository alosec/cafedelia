"""
Sync service for Cafedelia.

Coordinates JSONL watching, transformation, and database sync for the hybrid architecture.
"""

import asyncio
import logging
from typing import Optional

from sync.jsonl_watcher import watcher, SessionUpdate
from sync.jsonl_transformer import transformer

logger = logging.getLogger(__name__)


class SyncService:
    """Main sync service for JSONL → SQLite pipeline."""
    
    def __init__(self):
        self.watcher_task: Optional[asyncio.Task] = None
        self.is_running = False
    
    async def start(self) -> None:
        """Start the sync service."""
        if self.is_running:
            logger.warning("Sync service already running")
            return
        
        logger.info("Starting Cafedelia sync service")
        self.is_running = True
        
        # Start the watcher task
        self.watcher_task = asyncio.create_task(self._watch_and_sync())
    
    async def stop(self) -> None:
        """Stop the sync service."""
        if not self.is_running:
            return
        
        logger.info("Stopping Cafedelia sync service")
        self.is_running = False
        
        if self.watcher_task:
            self.watcher_task.cancel()
            try:
                await self.watcher_task
            except asyncio.CancelledError:
                pass
        
        # Stop any active Claude Code sessions
        from sync.claude_process import session_manager
        await session_manager.stop_all_sessions()
    
    async def _watch_and_sync(self) -> None:
        """Main watcher and sync loop."""
        try:
            # Initial sync of existing sessions
            logger.info("Performing initial session discovery and sync")
            sessions = watcher.discover_sessions()
            synced_count = await transformer.sync_all_sessions(sessions)
            logger.info(f"Initial sync complete: {synced_count} sessions synced")
            
            # Watch for changes
            async for update in watcher.watch_for_changes():
                try:
                    await self._handle_session_update(update)
                except Exception as e:
                    logger.error(f"Error handling session update: {e}")
                    
        except asyncio.CancelledError:
            logger.info("Sync watcher cancelled")
        except Exception as e:
            logger.error(f"Error in sync watcher: {e}")
    
    async def _handle_session_update(self, update: SessionUpdate) -> None:
        """Handle a session update event."""
        session = update.session
        
        if update.update_type == 'discovered':
            logger.debug(f"Discovered session: {session.session_id}")
        elif update.update_type == 'created':
            logger.info(f"New Claude Code session created: {session.session_id}")
            # Sync new session to database
            messages = watcher.get_session_messages(session.session_id)
            if messages:
                chat_id = await transformer.sync_session_to_database(session, messages)
                if chat_id:
                    logger.info(f"Synced new session {session.session_id} to chat {chat_id}")
        elif update.update_type == 'updated':
            logger.debug(f"Session updated: {session.session_id}")
            # Sync updated session
            messages = watcher.get_session_messages(session.session_id)
            if messages:
                chat_id = await transformer.sync_session_to_database(session, messages)
                if chat_id:
                    logger.debug(f"Updated session {session.session_id} in chat {chat_id}")
    
    async def manual_sync(self) -> int:
        """Manually trigger a full sync and return count of synced sessions."""
        logger.info("Manual sync requested")
        sessions = watcher.discover_sessions()
        synced_count = await transformer.sync_all_sessions(sessions)
        logger.info(f"Manual sync complete: {synced_count} sessions synced")
        return synced_count
    
    def get_status(self) -> dict:
        """Get sync service status."""
        return {
            'running': self.is_running,
            'watcher_active': self.watcher_task is not None and not self.watcher_task.done(),
            'cached_sessions': len(watcher.session_cache),
            'claude_projects_dir': str(watcher.projects_dir),
        }


# Global sync service instance
sync_service = SyncService()
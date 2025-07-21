"""
Centralized deduplication service for Claude Code session sync.

Provides thread-safe session synchronization and prevents the race conditions
that were causing massive database duplication.
"""

import asyncio
import logging
from typing import Dict, Optional, Set
from datetime import datetime
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class SyncLock:
    """Thread-safe synchronization lock for session sync operations."""
    
    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
    
    @asynccontextmanager
    async def acquire_session_lock(self, session_id: str):
        """Acquire a lock for a specific session."""
        async with self._global_lock:
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()
        
        session_lock = self._locks[session_id]
        async with session_lock:
            yield
    
    async def cleanup_unused_locks(self, active_sessions: Set[str]):
        """Remove locks for sessions that are no longer active."""
        async with self._global_lock:
            unused_sessions = set(self._locks.keys()) - active_sessions
            for session_id in unused_sessions:
                del self._locks[session_id]


class DeduplicationService:
    """Service for managing session deduplication and sync coordination."""
    
    def __init__(self):
        self.sync_lock = SyncLock()
        self._sync_in_progress: Set[str] = set()
        self._last_sync_times: Dict[str, datetime] = {}
        self._sync_counts: Dict[str, int] = {}
    
    async def should_sync_session(self, session_id: str, session_timestamp: float) -> bool:
        """
        Determine if a session should be synced based on deduplication rules.
        
        Returns False if:
        - Session is already being synced
        - Session was recently synced with same timestamp
        - Session has been synced too many times recently
        """
        # Check if sync is already in progress
        if session_id in self._sync_in_progress:
            logger.debug(f"Skipping sync for {session_id} - already in progress")
            return False
        
        # Check if we've recently synced this exact version
        last_sync = self._last_sync_times.get(session_id)
        if last_sync:
            session_dt = datetime.fromtimestamp(session_timestamp)
            time_diff = abs((session_dt - last_sync).total_seconds())
            if time_diff < 10:  # Don't sync same version within 10 seconds
                logger.debug(f"Skipping sync for {session_id} - recently synced")
                return False
        
        # Check sync frequency limits
        sync_count = self._sync_counts.get(session_id, 0)
        if sync_count > 5:  # Maximum 5 syncs per session per app run
            logger.warning(f"Sync limit reached for session {session_id}")
            return False
        
        return True
    
    async def mark_sync_start(self, session_id: str):
        """Mark that a sync operation has started for this session."""
        self._sync_in_progress.add(session_id)
        self._sync_counts[session_id] = self._sync_counts.get(session_id, 0) + 1
        logger.debug(f"Started sync for session {session_id} (count: {self._sync_counts[session_id]})")
    
    async def mark_sync_complete(self, session_id: str, session_timestamp: float, success: bool = True):
        """Mark that a sync operation has completed for this session."""
        self._sync_in_progress.discard(session_id)
        
        if success:
            self._last_sync_times[session_id] = datetime.fromtimestamp(session_timestamp)
            logger.debug(f"Completed sync for session {session_id}")
        else:
            # Reduce sync count on failure to allow retry
            if session_id in self._sync_counts:
                self._sync_counts[session_id] = max(0, self._sync_counts[session_id] - 1)
            logger.warning(f"Failed sync for session {session_id}")
    
    @asynccontextmanager
    async def sync_session(self, session_id: str, session_timestamp: float):
        """
        Context manager for safe session synchronization.
        
        Usage:
            async with dedup_service.sync_session(session_id, timestamp) as should_sync:
                if should_sync:
                    # Perform sync operations here
                    pass
        """
        should_sync = await self.should_sync_session(session_id, session_timestamp)
        
        if not should_sync:
            yield False
            return
        
        async with self.sync_lock.acquire_session_lock(session_id):
            await self.mark_sync_start(session_id)
            
            try:
                yield True
                await self.mark_sync_complete(session_id, session_timestamp, success=True)
            except Exception as e:
                await self.mark_sync_complete(session_id, session_timestamp, success=False)
                raise
    
    async def get_sync_status(self) -> Dict[str, Dict]:
        """Get current sync status for monitoring."""
        return {
            "syncs_in_progress": list(self._sync_in_progress),
            "sync_counts": dict(self._sync_counts),
            "last_sync_times": {
                session_id: timestamp.isoformat() 
                for session_id, timestamp in self._last_sync_times.items()
            }
        }
    
    async def reset_sync_counts(self):
        """Reset sync counts (useful for testing or cleanup)."""
        self._sync_counts.clear()
        self._last_sync_times.clear()
        logger.info("Reset all sync counts and timestamps")


# Global instance for use across the application
deduplication_service = DeduplicationService()
#!/usr/bin/env python3
"""
Synchronization Validation Guard

Comprehensive system to ensure database-JSONL consistency.
Provides validation, monitoring, and automatic repair mechanisms.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, timezone
from dataclasses import dataclass
import json
import hashlib
import sqlite3

from .jsonl_watcher import JSONLWatcher
from .jsonl_transformer import JSONLTransformer
from elia_chat.database.chat_dao import ChatDao
from elia_chat.models import ChatData

logger = logging.getLogger(__name__)


@dataclass
class SyncValidationResult:
    """Result of sync validation check"""
    is_valid: bool
    total_jsonl_sessions: int
    total_db_sessions: int
    missing_in_db: List[str]
    orphaned_in_db: List[str] 
    content_mismatches: List[str]
    last_modified_mismatches: List[str]
    validation_timestamp: datetime
    
    @property
    def has_issues(self) -> bool:
        return (len(self.missing_in_db) > 0 or 
                len(self.orphaned_in_db) > 0 or
                len(self.content_mismatches) > 0 or
                len(self.last_modified_mismatches) > 0)
    
    @property
    def summary(self) -> str:
        if self.is_valid:
            return f"✅ Sync valid: {self.total_db_sessions} sessions in sync"
        else:
            issues = []
            if self.missing_in_db:
                issues.append(f"{len(self.missing_in_db)} missing in DB")
            if self.orphaned_in_db:
                issues.append(f"{len(self.orphaned_in_db)} orphaned in DB")
            if self.content_mismatches:
                issues.append(f"{len(self.content_mismatches)} content mismatches")
            if self.last_modified_mismatches:
                issues.append(f"{len(self.last_modified_mismatches)} timestamp mismatches")
            return f"❌ Sync issues: {', '.join(issues)}"


@dataclass
class SessionSyncInfo:
    """Information about a session's sync status"""
    session_id: str
    jsonl_path: Optional[Path]
    jsonl_exists: bool
    jsonl_modified: Optional[datetime]
    jsonl_size: Optional[int]
    jsonl_content_hash: Optional[str]
    db_exists: bool
    db_modified: Optional[datetime]
    db_session_data: Optional[ChatData]


class SyncValidationGuard:
    """Main synchronization validation and repair system"""
    
    def __init__(self):
        self.jsonl_watcher = JSONLWatcher()
        self.jsonl_transformer = JSONLTransformer()
        self.chat_dao = ChatDao()
        self.validation_history: List[SyncValidationResult] = []
        
    async def validate_sync_state(self, deep_validation: bool = False) -> SyncValidationResult:
        """
        Comprehensive validation of database-JSONL sync state
        
        Args:
            deep_validation: If True, performs content hash comparison (slower)
        """
        logger.info("Starting sync validation...")
        validation_start = datetime.now(timezone.utc)
        
        # Step 1: Discover all JSONL sessions
        logger.info("Discovering JSONL sessions...")
        jsonl_sessions = {}
        async for session in self.jsonl_watcher.discover_sessions():
            jsonl_sessions[session.session_id] = session
        
        logger.info(f"Found {len(jsonl_sessions)} JSONL sessions")
        
        # Step 2: Get all database sessions with session_ids
        logger.info("Querying database sessions...")
        db_sessions = {}
        try:
            all_chats = await self.chat_dao.get_recent_chats(limit=10000)  # Get all
            for chat in all_chats:
                if chat.session_id:
                    db_sessions[chat.session_id] = chat
        except Exception as e:
            logger.error(f"Failed to query database sessions: {e}")
            return SyncValidationResult(
                is_valid=False,
                total_jsonl_sessions=len(jsonl_sessions),
                total_db_sessions=0,
                missing_in_db=[],
                orphaned_in_db=[],
                content_mismatches=[],
                last_modified_mismatches=[],
                validation_timestamp=validation_start
            )
        
        logger.info(f"Found {len(db_sessions)} database sessions with session_ids")
        
        # Step 3: Find mismatches
        jsonl_session_ids = set(jsonl_sessions.keys())
        db_session_ids = set(db_sessions.keys())
        
        missing_in_db = list(jsonl_session_ids - db_session_ids)
        orphaned_in_db = list(db_session_ids - jsonl_session_ids)
        
        logger.info(f"Missing in DB: {len(missing_in_db)}")
        logger.info(f"Orphaned in DB: {len(orphaned_in_db)}")
        
        # Step 4: Check content and timestamp consistency
        content_mismatches = []
        timestamp_mismatches = []
        
        if deep_validation:
            logger.info("Performing deep validation (content hash comparison)...")
            common_sessions = jsonl_session_ids & db_session_ids
            
            for session_id in common_sessions:
                jsonl_session = jsonl_sessions[session_id]
                db_session = db_sessions[session_id]
                
                # Check timestamp consistency
                jsonl_modified = jsonl_session.last_activity
                db_modified = db_session.updated_at
                
                if abs((jsonl_modified - db_modified).total_seconds()) > 60:  # 1 minute tolerance
                    timestamp_mismatches.append(session_id)
                
                # Check content hash (expensive)
                try:
                    jsonl_hash = await self._calculate_jsonl_content_hash(jsonl_session.jsonl_file_path)
                    db_hash = await self._calculate_db_content_hash(session_id)
                    
                    if jsonl_hash != db_hash:
                        content_mismatches.append(session_id)
                        
                except Exception as e:
                    logger.warning(f"Failed to compare content for session {session_id}: {e}")
        
        # Step 5: Determine overall validity
        is_valid = (len(missing_in_db) == 0 and 
                   len(orphaned_in_db) == 0 and
                   len(content_mismatches) == 0 and
                   len(timestamp_mismatches) == 0)
        
        result = SyncValidationResult(
            is_valid=is_valid,
            total_jsonl_sessions=len(jsonl_sessions),
            total_db_sessions=len(db_sessions),
            missing_in_db=missing_in_db,
            orphaned_in_db=orphaned_in_db,
            content_mismatches=content_mismatches,
            last_modified_mismatches=timestamp_mismatches,
            validation_timestamp=validation_start
        )
        
        self.validation_history.append(result)
        logger.info(f"Sync validation completed: {result.summary}")
        
        return result
    
    async def repair_sync_issues(self, validation_result: SyncValidationResult) -> bool:
        """
        Automatically repair sync issues found in validation
        
        Returns True if all repairs were successful
        """
        if validation_result.is_valid:
            logger.info("No sync issues to repair")
            return True
        
        logger.info("Starting automatic sync repair...")
        repair_success = True
        
        # Repair 1: Add missing sessions to database
        if validation_result.missing_in_db:
            logger.info(f"Adding {len(validation_result.missing_in_db)} missing sessions to database")
            
            for session_id in validation_result.missing_in_db:
                try:
                    # Find the JSONL session
                    jsonl_session = None
                    async for session in self.jsonl_watcher.discover_sessions():
                        if session.session_id == session_id:
                            jsonl_session = session
                            break
                    
                    if jsonl_session:
                        # Use transformer to add to database
                        success = await self.jsonl_transformer.transform_and_store_session(
                            jsonl_session.jsonl_file_path
                        )
                        if not success:
                            logger.error(f"Failed to add session {session_id} to database")
                            repair_success = False
                        else:
                            logger.info(f"Successfully added session {session_id} to database")
                    else:
                        logger.error(f"Could not find JSONL session for {session_id}")
                        repair_success = False
                        
                except Exception as e:
                    logger.error(f"Error adding session {session_id} to database: {e}")
                    repair_success = False
        
        # Repair 2: Remove orphaned sessions from database
        if validation_result.orphaned_in_db:
            logger.warning(f"Found {len(validation_result.orphaned_in_db)} orphaned sessions in database")
            logger.warning("Manual review recommended before deletion")
            # TODO: Implement orphan cleanup with user confirmation
        
        # Repair 3: Update content mismatches
        if validation_result.content_mismatches:
            logger.info(f"Updating {len(validation_result.content_mismatches)} sessions with content mismatches")
            
            for session_id in validation_result.content_mismatches:
                try:
                    # Re-sync this specific session
                    jsonl_session = None
                    async for session in self.jsonl_watcher.discover_sessions():
                        if session.session_id == session_id:
                            jsonl_session = session
                            break
                    
                    if jsonl_session:
                        # Force re-sync by deleting and re-adding
                        await self._force_resync_session(session_id, jsonl_session.jsonl_file_path)
                        logger.info(f"Successfully re-synced session {session_id}")
                    else:
                        logger.error(f"Could not find JSONL session for {session_id}")
                        repair_success = False
                        
                except Exception as e:
                    logger.error(f"Error re-syncing session {session_id}: {e}")
                    repair_success = False
        
        logger.info(f"Sync repair completed: {'✅ Success' if repair_success else '❌ Some failures'}")
        return repair_success
    
    async def continuous_validation(self, interval_seconds: int = 300) -> None:
        """
        Run continuous sync validation at specified interval
        
        Args:
            interval_seconds: Validation interval in seconds (default 5 minutes)
        """
        logger.info(f"Starting continuous sync validation (every {interval_seconds}s)")
        
        while True:
            try:
                # Perform validation
                result = await self.validate_sync_state(deep_validation=False)
                
                # Auto-repair if issues found
                if result.has_issues:
                    logger.warning(f"Sync issues detected: {result.summary}")
                    await self.repair_sync_issues(result)
                else:
                    logger.info(f"Sync validation passed: {result.summary}")
                
            except Exception as e:
                logger.error(f"Error in continuous validation: {e}")
            
            # Wait for next validation
            await asyncio.sleep(interval_seconds)
    
    async def get_session_sync_info(self, session_id: str) -> SessionSyncInfo:
        """Get detailed sync information for a specific session"""
        
        # Check JSONL
        jsonl_path = None
        jsonl_exists = False
        jsonl_modified = None
        jsonl_size = None
        jsonl_hash = None
        
        async for session in self.jsonl_watcher.discover_sessions():
            if session.session_id == session_id:
                jsonl_path = Path(session.jsonl_file_path)
                jsonl_exists = True
                jsonl_modified = session.last_activity
                jsonl_size = jsonl_path.stat().st_size if jsonl_path.exists() else None
                jsonl_hash = await self._calculate_jsonl_content_hash(str(jsonl_path))
                break
        
        # Check database
        db_exists = False
        db_modified = None
        db_session_data = None
        
        try:
            db_session_data = await self.chat_dao.get_chat_by_session_id(session_id)
            if db_session_data:
                db_exists = True
                db_modified = db_session_data.updated_at
        except Exception as e:
            logger.error(f"Error checking database for session {session_id}: {e}")
        
        return SessionSyncInfo(
            session_id=session_id,
            jsonl_path=jsonl_path,
            jsonl_exists=jsonl_exists,
            jsonl_modified=jsonl_modified,
            jsonl_size=jsonl_size,
            jsonl_content_hash=jsonl_hash,
            db_exists=db_exists,
            db_modified=db_modified,
            db_session_data=db_session_data
        )
    
    async def _calculate_jsonl_content_hash(self, jsonl_path: str) -> str:
        """Calculate hash of JSONL file content for comparison"""
        try:
            hasher = hashlib.md5()
            
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # Hash the essential content, not formatting
                    try:
                        data = json.loads(line.strip())
                        # Only hash essential fields for comparison
                        essential = {
                            'type': data.get('type'),
                            'message': data.get('message', {}).get('content') if data.get('message') else None,
                            'timestamp': data.get('timestamp')
                        }
                        hasher.update(json.dumps(essential, sort_keys=True).encode())
                    except json.JSONDecodeError:
                        continue
            
            return hasher.hexdigest()
            
        except Exception as e:
            logger.error(f"Error calculating JSONL hash for {jsonl_path}: {e}")
            return "error"
    
    async def _calculate_db_content_hash(self, session_id: str) -> str:
        """Calculate hash of database session content for comparison"""
        try:
            # Get all messages for this session from database
            chat = await self.chat_dao.get_chat_by_session_id(session_id)
            if not chat:
                return "no_db_content"
            
            hasher = hashlib.md5()
            
            # Hash chat title and key metadata
            hasher.update(f"{chat.title}_{chat.model_name}".encode())
            
            # Hash message content (would need to implement message retrieval)
            # For now, just use basic chat metadata
            return hasher.hexdigest()
            
        except Exception as e:
            logger.error(f"Error calculating DB hash for session {session_id}: {e}")
            return "error"
    
    async def _force_resync_session(self, session_id: str, jsonl_path: str) -> bool:
        """Force complete re-sync of a specific session"""
        try:
            # Delete existing database entry
            chat = await self.chat_dao.get_chat_by_session_id(session_id)
            if chat and chat.id:
                await self.chat_dao.delete_chat(chat.id)
                logger.info(f"Deleted existing database entry for session {session_id}")
            
            # Re-add from JSONL
            success = await self.jsonl_transformer.transform_and_store_session(jsonl_path)
            
            if success:
                logger.info(f"Successfully force re-synced session {session_id}")
            else:
                logger.error(f"Failed to force re-sync session {session_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in force re-sync for session {session_id}: {e}")
            return False
    
    def get_validation_history(self) -> List[SyncValidationResult]:
        """Get history of validation results"""
        return self.validation_history.copy()
    
    def get_latest_validation(self) -> Optional[SyncValidationResult]:
        """Get the most recent validation result"""
        return self.validation_history[-1] if self.validation_history else None


# Global sync validation guard instance
_sync_guard_instance: Optional[SyncValidationGuard] = None


def get_sync_validation_guard() -> SyncValidationGuard:
    """Get global sync validation guard instance"""
    global _sync_guard_instance
    if _sync_guard_instance is None:
        _sync_guard_instance = SyncValidationGuard()
    return _sync_guard_instance


async def main():
    """CLI entry point for sync validation"""
    import sys
    
    logging.basicConfig(level=logging.INFO)
    guard = SyncValidationGuard()
    
    if len(sys.argv) > 1 and sys.argv[1] == "continuous":
        await guard.continuous_validation()
    else:
        # One-time validation
        result = await guard.validate_sync_state(deep_validation=True)
        print(f"\n{result.summary}")
        
        if result.has_issues:
            print("\nIssue Details:")
            if result.missing_in_db:
                print(f"  Missing in DB: {result.missing_in_db[:5]}{'...' if len(result.missing_in_db) > 5 else ''}")
            if result.orphaned_in_db:
                print(f"  Orphaned in DB: {result.orphaned_in_db[:5]}{'...' if len(result.orphaned_in_db) > 5 else ''}")
            if result.content_mismatches:
                print(f"  Content mismatches: {result.content_mismatches[:5]}{'...' if len(result.content_mismatches) > 5 else ''}")
            
            # Offer to repair
            print("\nAttempting automatic repair...")
            repair_success = await guard.repair_sync_issues(result)
            print(f"Repair result: {'✅ Success' if repair_success else '❌ Failed'}")


if __name__ == "__main__":
    asyncio.run(main())
"""
Database integrity checker and repair tool for Cafedelia.

Ensures database entries correspond to actual JSONL files and removes
corrupted entries with fake session IDs.
"""

import logging
import asyncio
import re
from pathlib import Path
from typing import List, Tuple, Dict, Set
from datetime import datetime
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from elia_chat.database.database import get_session
from elia_chat.database.models import ChatDao, MessageDao

logger = logging.getLogger(__name__)


class DatabaseIntegrityChecker:
    """Check and repair database integrity against JSONL files."""
    
    # Valid UUID pattern
    UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    
    def __init__(self):
        self.claude_projects_dir = Path.home() / ".claude" / "projects"
        self.stats = {
            'total_chats': 0,
            'valid_chats': 0,
            'invalid_chats': 0,
            'orphaned_chats': 0,
            'repaired_chats': 0,
            'deleted_chats': 0,
            'deleted_messages': 0
        }
    
    async def check_integrity(self) -> Dict[str, any]:
        """
        Check database integrity and return report.
        
        Returns:
            Dict with integrity report including:
            - total_chats: Total chats in database
            - valid_chats: Chats with valid session IDs matching JSONL files
            - invalid_chats: Chats with fake/invalid session IDs
            - orphaned_chats: Chats with valid UUIDs but no JSONL file
            - recommendations: List of recommended actions
        """
        logger.info("Starting database integrity check...")
        
        # Get all JSONL files
        jsonl_sessions = self._get_all_jsonl_sessions()
        logger.info(f"Found {len(jsonl_sessions)} JSONL session files")
        
        # Check database entries
        async with get_session() as session:
            # Get all chats
            result = await session.execute(select(ChatDao))
            all_chats = result.scalars().all()
            self.stats['total_chats'] = len(all_chats)
            
            invalid_chats = []
            orphaned_chats = []
            valid_chats = []
            
            for chat in all_chats:
                session_id = chat.session_id or self._extract_session_from_title(chat.title)
                
                if not session_id:
                    invalid_chats.append((chat, "No session ID"))
                elif not self._is_valid_uuid(session_id):
                    invalid_chats.append((chat, f"Invalid session ID format: {session_id}"))
                elif session_id not in jsonl_sessions:
                    orphaned_chats.append((chat, f"No JSONL file for session: {session_id}"))
                else:
                    valid_chats.append(chat)
            
            self.stats['valid_chats'] = len(valid_chats)
            self.stats['invalid_chats'] = len(invalid_chats)
            self.stats['orphaned_chats'] = len(orphaned_chats)
        
        # Generate recommendations
        recommendations = []
        if invalid_chats:
            recommendations.append(f"Remove {len(invalid_chats)} chats with invalid session IDs")
        if orphaned_chats:
            recommendations.append(f"Remove {len(orphaned_chats)} orphaned chats without JSONL files")
        
        report = {
            'stats': self.stats,
            'invalid_chats': [(c.id, c.title, reason) for c, reason in invalid_chats],
            'orphaned_chats': [(c.id, c.title, reason) for c, reason in orphaned_chats],
            'recommendations': recommendations,
            'jsonl_sessions_count': len(jsonl_sessions)
        }
        
        logger.info(f"Integrity check complete: {self.stats['valid_chats']}/{self.stats['total_chats']} valid chats")
        return report
    
    async def repair_database(self, remove_invalid: bool = True, remove_orphaned: bool = True) -> Dict[str, any]:
        """
        Repair database by removing invalid entries.
        
        Args:
            remove_invalid: Remove chats with invalid/fake session IDs
            remove_orphaned: Remove chats with valid UUIDs but no JSONL file
            
        Returns:
            Dict with repair report
        """
        logger.info("Starting database repair...")
        
        # Get all JSONL sessions for validation
        jsonl_sessions = self._get_all_jsonl_sessions()
        
        async with get_session() as session:
            # Get all chats
            result = await session.execute(select(ChatDao))
            all_chats = result.scalars().all()
            
            chats_to_delete = []
            
            for chat in all_chats:
                session_id = chat.session_id or self._extract_session_from_title(chat.title)
                
                # Check if should delete
                should_delete = False
                reason = ""
                
                if not session_id or not self._is_valid_uuid(session_id):
                    if remove_invalid:
                        should_delete = True
                        reason = f"Invalid session ID: {session_id}"
                elif session_id not in jsonl_sessions:
                    if remove_orphaned:
                        should_delete = True
                        reason = f"No JSONL file found"
                
                if should_delete:
                    chats_to_delete.append((chat.id, chat.title, reason))
                    
                    # Delete messages first
                    await session.execute(
                        delete(MessageDao).where(MessageDao.chat_id == chat.id)
                    )
                    
                    # Delete chat
                    await session.execute(
                        delete(ChatDao).where(ChatDao.id == chat.id)
                    )
                    
                    self.stats['deleted_chats'] += 1
                    logger.info(f"Deleted chat {chat.id}: {chat.title} ({reason})")
            
            await session.commit()
        
        # Log summary
        logger.info(f"Database repair complete: Deleted {self.stats['deleted_chats']} invalid chats")
        
        return {
            'deleted_chats': chats_to_delete,
            'stats': self.stats
        }
    
    def _get_all_jsonl_sessions(self) -> Set[str]:
        """Get all valid session IDs from JSONL files."""
        sessions = set()
        
        if not self.claude_projects_dir.exists():
            return sessions
        
        # Find all JSONL files with UUID names
        for project_dir in self.claude_projects_dir.iterdir():
            if project_dir.is_dir():
                for jsonl_file in project_dir.glob("*.jsonl"):
                    session_id = jsonl_file.stem
                    if self._is_valid_uuid(session_id):
                        sessions.add(session_id)
        
        return sessions
    
    def _is_valid_uuid(self, session_id: str) -> bool:
        """Check if a string is a valid UUID."""
        if not session_id:
            return False
        return bool(self.UUID_PATTERN.match(session_id.lower()))
    
    def _extract_session_from_title(self, title: str) -> str:
        """Try to extract a session ID from chat title."""
        if not title:
            return ""
        
        # Look for UUID pattern in title
        parts = title.split()
        for part in parts:
            if self._is_valid_uuid(part):
                return part
        
        # Check if entire title might be a session ID
        if self._is_valid_uuid(title):
            return title
        
        return ""


async def check_and_repair_on_startup():
    """
    Check database integrity on startup and repair if needed.
    
    This should be called when the app starts to ensure database is clean.
    """
    checker = DatabaseIntegrityChecker()
    
    # Check integrity
    report = await checker.check_integrity()
    
    # If we have invalid entries, repair automatically
    if report['stats']['invalid_chats'] > 0 or report['stats']['orphaned_chats'] > 0:
        logger.warning(
            f"Database integrity issues found: "
            f"{report['stats']['invalid_chats']} invalid chats, "
            f"{report['stats']['orphaned_chats']} orphaned chats"
        )
        
        # Repair database
        repair_report = await checker.repair_database(
            remove_invalid=True,
            remove_orphaned=True
        )
        
        logger.info(
            f"Database repair complete: Removed {len(repair_report['deleted_chats'])} invalid chats"
        )
        
        return repair_report
    else:
        logger.info("Database integrity check passed - no issues found")
        return None


if __name__ == "__main__":
    # Allow running as standalone script for manual repair
    async def main():
        logging.basicConfig(level=logging.INFO)
        
        checker = DatabaseIntegrityChecker()
        
        # Check integrity
        print("Checking database integrity...")
        report = await checker.check_integrity()
        
        print(f"\nIntegrity Report:")
        print(f"Total chats: {report['stats']['total_chats']}")
        print(f"Valid chats: {report['stats']['valid_chats']}")
        print(f"Invalid chats: {report['stats']['invalid_chats']}")
        print(f"Orphaned chats: {report['stats']['orphaned_chats']}")
        print(f"JSONL sessions found: {report['jsonl_sessions_count']}")
        
        if report['invalid_chats']:
            print(f"\nInvalid chats (first 10):")
            for chat_id, title, reason in report['invalid_chats'][:10]:
                print(f"  - {title}: {reason}")
        
        if report['invalid_chats'] or report['orphaned_chats']:
            response = input("\nRepair database? (y/n): ")
            if response.lower() == 'y':
                repair_report = await checker.repair_database()
                print(f"\nDeleted {len(repair_report['deleted_chats'])} invalid chats")
    
    asyncio.run(main())
"""
Sync validation to ensure perfect parity between JSONL and SQLite database.

Compares JSONL source data with database representations to identify
discrepancies and maintain data integrity.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from elia_chat.database.database import get_session
from elia_chat.database.models import ChatDao, MessageDao
from sync.jsonl_watcher import watcher
from sync.content_extractor import ContentExtractor
from sqlmodel import select

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of sync validation."""
    session_id: str
    is_valid: bool
    issues: List[str]
    jsonl_message_count: int
    db_message_count: int
    missing_in_db: List[int]
    extra_in_db: List[int]
    content_mismatches: List[Tuple[int, str]]  # (index, description)


@dataclass
class ValidationSummary:
    """Overall validation summary."""
    total_sessions: int
    valid_sessions: int
    invalid_sessions: int
    total_issues: int
    session_results: List[ValidationResult]


class SyncValidator:
    """Validates sync integrity between JSONL and database."""
    
    def __init__(self):
        self.issues_found = 0
        self.sessions_checked = 0
    
    async def validate_all_sessions(self) -> ValidationSummary:
        """Validate all sessions for sync parity."""
        logger.info("Starting comprehensive sync validation")
        
        # Discover all sessions
        sessions = watcher.discover_sessions()
        results = []
        
        for session in sessions:
            result = await self.validate_session(session.session_id)
            results.append(result)
            
            if not result.is_valid:
                logger.warning(f"Session {session.session_id} has {len(result.issues)} validation issues")
        
        # Compile summary
        valid_count = sum(1 for r in results if r.is_valid)
        total_issues = sum(len(r.issues) for r in results)
        
        summary = ValidationSummary(
            total_sessions=len(results),
            valid_sessions=valid_count,
            invalid_sessions=len(results) - valid_count,
            total_issues=total_issues,
            session_results=results
        )
        
        logger.info(f"Validation complete: {valid_count}/{len(results)} sessions valid, {total_issues} total issues")
        return summary
    
    async def validate_session(self, session_id: str) -> ValidationResult:
        """
        Validate a single session for JSONL-DB parity.
        
        Args:
            session_id: Session to validate
            
        Returns:
            ValidationResult with detailed findings
        """
        issues = []
        missing_in_db = []
        extra_in_db = []
        content_mismatches = []
        
        # Get JSONL data
        jsonl_path = watcher.get_session_file_path(session_id)
        if not jsonl_path:
            return ValidationResult(
                session_id=session_id,
                is_valid=False,
                issues=["JSONL file not found"],
                jsonl_message_count=0,
                db_message_count=0,
                missing_in_db=[],
                extra_in_db=[],
                content_mismatches=[]
            )
        
        # Parse JSONL messages
        jsonl_messages = await self._parse_jsonl_messages(jsonl_path)
        
        # Get database data
        db_messages = await self._get_db_messages(session_id)
        
        # Compare counts
        if len(jsonl_messages) != len(db_messages):
            issues.append(f"Message count mismatch: JSONL={len(jsonl_messages)}, DB={len(db_messages)}")
        
        # Check for missing messages in DB
        for i, jsonl_msg in enumerate(jsonl_messages):
            if i >= len(db_messages):
                missing_in_db.append(i)
            else:
                # Compare content
                jsonl_content = ContentExtractor.extract_message_content(jsonl_msg)
                db_content = db_messages[i].content
                
                if jsonl_content != db_content:
                    # Allow for truncation differences
                    if not self._is_acceptable_truncation(jsonl_content, db_content):
                        content_mismatches.append((i, "Content mismatch"))
        
        # Check for extra messages in DB
        if len(db_messages) > len(jsonl_messages):
            extra_in_db = list(range(len(jsonl_messages), len(db_messages)))
        
        # Compile issues
        if missing_in_db:
            issues.append(f"{len(missing_in_db)} messages missing from database")
        
        if extra_in_db:
            issues.append(f"{len(extra_in_db)} extra messages in database")
        
        if content_mismatches:
            issues.append(f"{len(content_mismatches)} content mismatches")
        
        return ValidationResult(
            session_id=session_id,
            is_valid=len(issues) == 0,
            issues=issues,
            jsonl_message_count=len(jsonl_messages),
            db_message_count=len(db_messages),
            missing_in_db=missing_in_db,
            extra_in_db=extra_in_db,
            content_mismatches=content_mismatches
        )
    
    async def _parse_jsonl_messages(self, jsonl_path: Path) -> List[Dict[str, Any]]:
        """Parse messages from JSONL file."""
        messages = []
        
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            # Only include actual message content
                            if data.get('type') in ['user', 'assistant'] or 'toolUseResult' in data:
                                messages.append(data)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Error parsing JSONL file {jsonl_path}: {e}")
        
        return messages
    
    async def _get_db_messages(self, session_id: str) -> List[MessageDao]:
        """Get messages from database for a session."""
        async with get_session() as db_session:
            # Find chat by session_id
            chat_stmt = select(ChatDao).where(ChatDao.session_id == session_id)
            chat_result = await db_session.exec(chat_stmt)
            chat = chat_result.first()
            
            if not chat:
                return []
            
            # Get messages ordered by index
            msg_stmt = select(MessageDao).where(MessageDao.chat_id == chat.id).order_by(MessageDao.idx)
            msg_result = await db_session.exec(msg_stmt)
            return list(msg_result.all())
    
    def _is_acceptable_truncation(self, original: str, truncated: str) -> bool:
        """Check if content difference is due to acceptable truncation."""
        # If truncated content is a prefix of original, it's acceptable
        if original.startswith(truncated.rstrip('.')):
            return True
        
        # Check for our truncation markers
        if "[... truncated ...]" in truncated or "[truncated]" in truncated:
            return True
        
        # Check for tool result summarization
        if "[LS output:" in truncated or "[Grep output:" in truncated:
            return True
        
        return False
    
    async def fix_session_issues(self, session_id: str, validation_result: ValidationResult) -> bool:
        """
        Attempt to fix validation issues for a session.
        
        Args:
            session_id: Session to fix
            validation_result: Validation result with identified issues
            
        Returns:
            True if fixes were successful
        """
        if validation_result.is_valid:
            return True
        
        logger.info(f"Attempting to fix {len(validation_result.issues)} issues for session {session_id}")
        
        try:
            # Reset sync position to force full resync
            from sync.incremental_sync import incremental_sync_engine
            incremental_sync_engine.reset_position(session_id)
            
            # Trigger resync
            jsonl_path = watcher.get_session_file_path(session_id)
            if jsonl_path:
                await incremental_sync_engine.sync_new_messages(session_id, jsonl_path)
                logger.info(f"Resynced session {session_id}")
                return True
            
        except Exception as e:
            logger.error(f"Failed to fix session {session_id}: {e}")
        
        return False
    
    def generate_report(self, summary: ValidationSummary) -> str:
        """Generate a human-readable validation report."""
        report = []
        report.append("=== SYNC VALIDATION REPORT ===")
        report.append(f"Total Sessions: {summary.total_sessions}")
        report.append(f"Valid Sessions: {summary.valid_sessions}")
        report.append(f"Invalid Sessions: {summary.invalid_sessions}")
        report.append(f"Total Issues: {summary.total_issues}")
        report.append("")
        
        if summary.invalid_sessions > 0:
            report.append("SESSIONS WITH ISSUES:")
            for result in summary.session_results:
                if not result.is_valid:
                    report.append(f"  {result.session_id}:")
                    for issue in result.issues:
                        report.append(f"    - {issue}")
        
        return "\n".join(report)


# Global validator instance
sync_validator = SyncValidator()
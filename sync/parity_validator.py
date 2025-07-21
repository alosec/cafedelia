"""
JSONL-Database parity validation and automatic correction.

Ensures the database accurately reflects the state of JSONL files by detecting
inconsistencies and automatically correcting them. JSONL files are treated as
the authoritative source of truth.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

from elia_chat.database.database import get_session
from elia_chat.database.models import MessageDao, ChatDao
from sqlalchemy import select, delete
from .message_parser import MessageParser

logger = logging.getLogger(__name__)


class ParityIssue:
    """Represents a detected parity issue between JSONL and database."""
    
    def __init__(self, session_id: str, issue_type: str, details: Dict[str, Any]):
        self.session_id = session_id
        self.issue_type = issue_type  # 'missing_messages', 'extra_messages', 'content_mismatch'
        self.details = details
        self.detected_at = datetime.now()
    
    def __repr__(self):
        return f"ParityIssue({self.session_id}, {self.issue_type}, {self.details})"


class ParityValidator:
    """
    Validates and corrects JSONL-database consistency.
    
    Core principles:
    - JSONL files are the authoritative source of truth
    - Database must accurately reflect JSONL state
    - Automatic correction prioritizes data preservation
    - All corrections are logged for audit trails
    """
    
    def __init__(self):
        self.message_parser = MessageParser()
        self.correction_stats = {
            'sessions_corrected': 0,
            'messages_added': 0,
            'messages_removed': 0,
            'last_correction': None
        }
    
    async def validate_session_parity(self, session_state) -> List[ParityIssue]:
        """
        Comprehensive parity validation for a session.
        
        Args:
            session_state: SessionState object to validate
            
        Returns:
            List of detected parity issues
        """
        issues = []
        
        try:
            # Load JSONL messages
            jsonl_messages = await self._load_jsonl_messages(session_state.jsonl_path)
            
            # Load database messages
            database_messages = await self._load_database_messages(session_state.session_id)
            
            # Compare counts
            if len(jsonl_messages) != len(database_messages):
                issues.append(ParityIssue(
                    session_state.session_id,
                    'count_mismatch',
                    {
                        'jsonl_count': len(jsonl_messages),
                        'database_count': len(database_messages),
                        'difference': len(jsonl_messages) - len(database_messages)
                    }
                ))
            
            # Detailed message comparison
            detailed_issues = await self._compare_message_sequences(
                session_state.session_id, jsonl_messages, database_messages
            )
            issues.extend(detailed_issues)
            
            if issues:
                logger.warning(f"Detected {len(issues)} parity issues for session {session_state.session_id}")
            else:
                logger.debug(f"Session {session_state.session_id} has perfect parity")
            
            return issues
            
        except Exception as e:
            logger.error(f"Error validating parity for session {session_state.session_id}: {e}")
            return [ParityIssue(
                session_state.session_id,
                'validation_error',
                {'error': str(e)}
            )]
    
    async def _load_jsonl_messages(self, jsonl_path: Path) -> List[Dict[str, Any]]:
        """Load and parse all messages from a JSONL file."""
        messages = []
        
        if not jsonl_path.exists():
            logger.warning(f"JSONL file does not exist: {jsonl_path}")
            return messages
        
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        message_data = json.loads(line)
                        # Add line number for debugging
                        message_data['_jsonl_line'] = line_num
                        messages.append(message_data)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON on line {line_num} in {jsonl_path}: {e}")
                        continue
            
            logger.debug(f"Loaded {len(messages)} messages from {jsonl_path}")
            return messages
            
        except Exception as e:
            logger.error(f"Error reading JSONL file {jsonl_path}: {e}")
            return []
    
    async def _load_database_messages(self, session_id: str) -> List[MessageDao]:
        """Load all messages for a session from the database."""
        try:
            async with get_session() as db_session:
                # Get chat ID
                result = await db_session.execute(
                    select(ChatDao.id).where(ChatDao.session_id == session_id)
                )
                chat_id = result.scalar_one_or_none()
                
                if not chat_id:
                    logger.debug(f"No chat found for session {session_id}")
                    return []
                
                # Get all messages ordered by timestamp
                result = await db_session.execute(
                    select(MessageDao)
                    .where(MessageDao.chat_id == chat_id)
                    .order_by(MessageDao.timestamp)
                )
                messages = result.scalars().all()
                
                logger.debug(f"Loaded {len(messages)} database messages for session {session_id}")
                return list(messages)
                
        except Exception as e:
            logger.error(f"Error loading database messages for session {session_id}: {e}")
            return []
    
    async def _compare_message_sequences(
        self, 
        session_id: str, 
        jsonl_messages: List[Dict[str, Any]], 
        database_messages: List[MessageDao]
    ) -> List[ParityIssue]:
        """
        Detailed comparison of message sequences to identify specific issues.
        """
        issues = []
        
        # Parse JSONL messages for comparison
        parsed_jsonl = []
        for jsonl_msg in jsonl_messages:
            try:
                parsed_msg = self.message_parser.parse_claude_message(
                    json.dumps(jsonl_msg), session_id
                )
                if parsed_msg:
                    parsed_msg._jsonl_line = jsonl_msg.get('_jsonl_line')
                    parsed_jsonl.append(parsed_msg)
            except Exception as e:
                logger.warning(f"Failed to parse JSONL message: {e}")
                continue
        
        # Compare by position/sequence
        min_length = min(len(parsed_jsonl), len(database_messages))
        
        for i in range(min_length):
            jsonl_msg = parsed_jsonl[i]
            db_msg = database_messages[i]
            
            # Content comparison
            if jsonl_msg.content != db_msg.content:
                issues.append(ParityIssue(
                    session_id,
                    'content_mismatch',
                    {
                        'position': i,
                        'jsonl_content_length': len(jsonl_msg.content),
                        'database_content_length': len(db_msg.content),
                        'database_message_id': db_msg.id,
                        'jsonl_line': getattr(jsonl_msg, '_jsonl_line', None)
                    }
                ))
            
            # Message type comparison
            if jsonl_msg.message_type != db_msg.message_type:
                issues.append(ParityIssue(
                    session_id,
                    'type_mismatch',
                    {
                        'position': i,
                        'jsonl_type': jsonl_msg.message_type,
                        'database_type': db_msg.message_type,
                        'database_message_id': db_msg.id,
                        'jsonl_line': getattr(jsonl_msg, '_jsonl_line', None)
                    }
                ))
        
        # Missing messages in database
        if len(parsed_jsonl) > len(database_messages):
            missing_count = len(parsed_jsonl) - len(database_messages)
            missing_start = len(database_messages)
            
            issues.append(ParityIssue(
                session_id,
                'missing_messages',
                {
                    'count': missing_count,
                    'start_position': missing_start,
                    'missing_lines': [
                        getattr(msg, '_jsonl_line', None) 
                        for msg in parsed_jsonl[missing_start:]
                    ]
                }
            ))
        
        # Extra messages in database
        elif len(database_messages) > len(parsed_jsonl):
            extra_count = len(database_messages) - len(parsed_jsonl)
            extra_start = len(parsed_jsonl)
            
            issues.append(ParityIssue(
                session_id,
                'extra_messages',
                {
                    'count': extra_count,
                    'start_position': extra_start,
                    'extra_message_ids': [
                        msg.id for msg in database_messages[extra_start:]
                    ]
                }
            ))
        
        return issues
    
    async def correct_session_parity(self, session_state) -> bool:
        """
        Automatically correct parity issues by syncing database to JSONL.
        
        Args:
            session_state: SessionState object to correct
            
        Returns:
            True if correction successful, False otherwise
        """
        try:
            logger.info(f"Starting parity correction for session {session_state.session_id}")
            
            # Validate current state
            issues = await self.validate_session_parity(session_state)
            if not issues:
                logger.info(f"No parity issues found for session {session_state.session_id}")
                return True
            
            # Load JSONL as source of truth
            jsonl_messages = await self._load_jsonl_messages(session_state.jsonl_path)
            
            # Clear existing database messages for this session
            async with get_session() as db_session:
                if session_state.chat_dao:
                    # Delete existing messages
                    await db_session.execute(
                        delete(MessageDao).where(MessageDao.chat_id == session_state.chat_dao.id)
                    )
                    
                    logger.info(f"Cleared {session_state.database_message_count} existing messages")
                    self.correction_stats['messages_removed'] += session_state.database_message_count
                
                # Re-import all messages from JSONL
                from .persistence_coordinator import persistence_coordinator
                imported_count = 0
                
                for jsonl_msg in jsonl_messages:
                    try:
                        # Parse message
                        parsed_msg = self.message_parser.parse_claude_message(
                            json.dumps(jsonl_msg), session_state.session_id
                        )
                        
                        if parsed_msg:
                            # Persist to database
                            message_dao = await persistence_coordinator.persist_message(
                                parsed_msg, session_state.chat_dao, db_session
                            )
                            
                            if message_dao:
                                imported_count += 1
                            else:
                                logger.warning(f"Failed to import message from line {jsonl_msg.get('_jsonl_line')}")
                    
                    except Exception as e:
                        logger.warning(f"Error importing JSONL message: {e}")
                        continue
                
                await db_session.commit()
                
                logger.info(f"Imported {imported_count} messages from JSONL")
                self.correction_stats['messages_added'] += imported_count
                self.correction_stats['sessions_corrected'] += 1
                self.correction_stats['last_correction'] = datetime.now()
                
                # Update session state
                session_state.database_message_count = imported_count
                session_state.has_parity_issues = False
                
                return True
                
        except Exception as e:
            logger.error(f"Error correcting parity for session {session_state.session_id}: {e}")
            return False
    
    async def validate_all_sessions(self, session_states: Dict[str, Any]) -> Dict[str, List[ParityIssue]]:
        """
        Validate parity for all active sessions.
        
        Returns:
            Dictionary mapping session_id to list of issues
        """
        all_issues = {}
        
        for session_id, session_state in session_states.items():
            try:
                issues = await self.validate_session_parity(session_state)
                if issues:
                    all_issues[session_id] = issues
            except Exception as e:
                logger.error(f"Error validating session {session_id}: {e}")
                all_issues[session_id] = [ParityIssue(
                    session_id, 'validation_error', {'error': str(e)}
                )]
        
        return all_issues
    
    def get_correction_stats(self) -> Dict[str, Any]:
        """Get statistics about corrections performed."""
        stats = self.correction_stats.copy()
        if stats['last_correction']:
            stats['last_correction'] = stats['last_correction'].isoformat()
        return stats
    
    async def generate_parity_report(self, session_id: str) -> Dict[str, Any]:
        """
        Generate a comprehensive parity report for a session.
        
        Returns:
            Detailed report with statistics and recommendations
        """
        # This would be used for detailed debugging and monitoring
        # Implementation would include detailed analysis of JSONL vs DB state
        pass


# Global instance for use across the application
parity_validator = ParityValidator()
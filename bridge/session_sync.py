"""
Session synchronization between cafed backend and Elia database
"""

import asyncio
from datetime import datetime
from typing import List, Optional
from sqlmodel import select

from bridge.cafed_client import CafedClient, ClaudeSession
from elia_chat.database.database import get_session
from elia_chat.database.models import ChatDao, MessageDao


class SessionSync:
    """Synchronizes Claude Code sessions with Elia database"""
    
    def __init__(self, cafed_client: Optional[CafedClient] = None):
        self.cafed_client = cafed_client or CafedClient()
    
    async def sync_all_sessions(self) -> dict:
        """Sync all Claude Code sessions from cafed backend to Elia database using ChatDao/MessageDao"""
        try:
            # Fetch sessions from cafed backend
            sessions = await self.cafed_client.get_sessions()
            
            results = {
                'total_fetched': len(sessions),
                'created': 0,
                'updated': 0,
                'errors': []
            }
            
            async with get_session() as db_session:
                for session in sessions:
                    try:
                        # Check if chat already exists by looking for session UUID in meta
                        existing_query = select(ChatDao).join(MessageDao).where(
                            MessageDao.meta.op('->>')('sessionId') == session.session_uuid
                        )
                        existing_result = await db_session.exec(existing_query)
                        existing_chat = existing_result.first()
                        
                        if existing_chat:
                            # Update existing chat title and model if needed
                            if not existing_chat.title or existing_chat.title.startswith("Claude Code Session ("):
                                existing_chat.title = session.title
                            db_session.add(existing_chat)
                            results['updated'] += 1
                        else:
                            # Create new chat for this live session
                            new_chat = ChatDao(
                                title=session.title,
                                model="claude-sonnet-4-live",
                                started_at=session.created_at
                            )
                            db_session.add(new_chat)
                            await db_session.commit()  # Get chat.id
                            
                            # Create summary message with session metadata
                            summary_message = MessageDao(
                                chat_id=new_chat.id,
                                role="assistant",
                                content=f"Claude Code session summary:\n• Project: {session.project_name}\n• Path: {session.project_path}\n• Status: {session.status}\n• Turns: {session.conversation_turns}\n• Last activity: {session.last_activity}",
                                timestamp=session.last_activity,
                                model="claude-sonnet-4-live",
                                meta={
                                    "sessionId": session.session_uuid,
                                    "project_name": session.project_name,
                                    "project_path": session.project_path,
                                    "status": session.status,
                                    "conversation_turns": session.conversation_turns,
                                    "total_cost_usd": session.total_cost_usd,
                                    "file_operations": session.file_operations,
                                    "jsonl_file_path": session.jsonl_file_path,
                                    "sync_source": "cafed_backend"
                                }
                            )
                            db_session.add(summary_message)
                            results['created'] += 1
                            
                    except Exception as e:
                        results['errors'].append({
                            'session_uuid': session.session_uuid,
                            'error': str(e)
                        })
                
                await db_session.commit()
            
            return results
            
        except Exception as e:
            return {
                'total_fetched': 0,
                'created': 0, 
                'updated': 0,
                'errors': [{'error': f'Failed to fetch sessions: {str(e)}'}]
            }
    
    async def sync_session(self, session_uuid: str) -> bool:
        """Sync a specific Claude Code session using ChatDao/MessageDao"""
        try:
            # Fetch specific session from cafed backend
            session = await self.cafed_client.get_session(session_uuid)
            
            if not session:
                return False
            
            async with get_session() as db_session:
                # Check if chat already exists by looking for session UUID in meta
                existing_query = select(ChatDao).join(MessageDao).where(
                    MessageDao.meta.op('->>')('sessionId') == session_uuid
                )
                existing_result = await db_session.exec(existing_query)
                existing_chat = existing_result.first()
                
                if existing_chat:
                    # Update existing chat title to reflect current status
                    existing_chat.title = session.title
                    db_session.add(existing_chat)
                else:
                    # Create new chat for this live session
                    new_chat = ChatDao(
                        title=session.title,
                        model="claude-sonnet-4-live",
                        started_at=session.created_at
                    )
                    db_session.add(new_chat)
                    await db_session.commit()  # Get chat.id
                    
                    # Create summary message with session metadata
                    summary_message = MessageDao(
                        chat_id=new_chat.id,
                        role="assistant",
                        content=f"Claude Code session summary:\n• Project: {session.project_name}\n• Path: {session.project_path}\n• Status: {session.status}\n• Turns: {session.conversation_turns}\n• Last activity: {session.last_activity}",
                        timestamp=session.last_activity,
                        model="claude-sonnet-4-live",
                        meta={
                            "sessionId": session.session_uuid,
                            "project_name": session.project_name,
                            "project_path": session.project_path,
                            "status": session.status,
                            "conversation_turns": session.conversation_turns,
                            "total_cost_usd": session.total_cost_usd,
                            "file_operations": session.file_operations,
                            "jsonl_file_path": session.jsonl_file_path,
                            "sync_source": "cafed_backend"
                        }
                    )
                    db_session.add(summary_message)
                
                await db_session.commit()
            
            return True
            
        except Exception as e:
            print(f"Failed to sync session {session_uuid}: {e}")
            return False
    
    async def get_local_sessions(self) -> List[ChatDao]:
        """Get all Claude Code sessions from local database"""
        async with get_session() as db_session:
            # Find chats that have messages with sessionId in meta (indicating Claude Code sessions)
            statement = (
                select(ChatDao)
                .join(MessageDao)
                .where(MessageDao.meta.op('->>')('sessionId').isnot(None))
                .order_by(ChatDao.started_at.desc())
                .distinct()
            )
            result = await db_session.exec(statement)
            return list(result)
    
    async def get_active_sessions(self) -> List[ChatDao]:
        """Get active Claude Code sessions from local database"""
        async with get_session() as db_session:
            # Find chats with active status in message meta
            statement = (
                select(ChatDao)
                .join(MessageDao)
                .where(
                    MessageDao.meta.op('->>')('status') == 'active',
                    MessageDao.meta.op('->>')('sessionId').isnot(None)
                )
                .order_by(ChatDao.started_at.desc())
                .distinct()
            )
            result = await db_session.exec(statement)
            return list(result)
    
    async def get_project_sessions(self, project_path: str) -> List[ChatDao]:
        """Get sessions for a specific project from local database"""
        async with get_session() as db_session:
            # Find chats for specific project path
            statement = (
                select(ChatDao)
                .join(MessageDao)
                .where(
                    MessageDao.meta.op('->>')('project_path') == project_path,
                    MessageDao.meta.op('->>')('sessionId').isnot(None)
                )
                .order_by(ChatDao.started_at.desc())
                .distinct()
            )
            result = await db_session.exec(statement)
            return list(result)
    
    async def add_intelligence(
        self,
        session_uuid: str,
        summary_type: str,
        summary_content: str,
        confidence_score: float = 1.0,
        metadata: Optional[dict] = None
    ) -> bool:
        """Add intelligence summary for a session as a new message"""
        try:
            async with get_session() as db_session:
                # Find the chat for this session
                chat_query = select(ChatDao).join(MessageDao).where(
                    MessageDao.meta.op('->>')('sessionId') == session_uuid
                )
                chat_result = await db_session.exec(chat_query)
                chat = chat_result.first()
                
                if not chat:
                    print(f"No chat found for session {session_uuid}")
                    return False
                
                # Create intelligence message
                intelligence_message = MessageDao(
                    chat_id=chat.id,
                    role="assistant",
                    content=f"🧠 **{summary_type.title()} Intelligence**\n\n{summary_content}",
                    timestamp=datetime.now(),
                    model="claude-intelligence",
                    meta={
                        "sessionId": session_uuid,
                        "intelligence_type": summary_type,
                        "confidence_score": confidence_score,
                        "intelligence_metadata": metadata or {},
                        "sync_source": "intelligence_system"
                    }
                )
                
                db_session.add(intelligence_message)
                await db_session.commit()
                
                return True
                
        except Exception as e:
            print(f"Failed to add intelligence for session {session_uuid}: {e}")
            return False
    
    async def health_check(self) -> dict:
        """Check health of both cafed backend and local database"""
        try:
            # Check cafed backend
            cafed_health = await self.cafed_client.health_check()
            
            # Check local database by counting Claude Code sessions
            local_sessions = await self.get_local_sessions()
            
            # Count imported vs live sessions
            async with get_session() as db_session:
                imported_count_query = select(ChatDao).join(MessageDao).where(
                    MessageDao.meta.op('->>')('sessionId').isnot(None),
                    MessageDao.meta.op('->>')('sync_source').is_(None)  # Imported sessions don't have sync_source
                )
                imported_result = await db_session.exec(imported_count_query)
                imported_count = len(list(imported_result))
                
                live_count_query = select(ChatDao).join(MessageDao).where(
                    MessageDao.meta.op('->>')('sync_source') == 'cafed_backend'
                )
                live_result = await db_session.exec(live_count_query)
                live_count = len(list(live_result))
            
            return {
                'cafed_backend': {
                    'status': cafed_health.get('status', 'unknown'),
                    'service': cafed_health.get('service', 'unknown')
                },
                'local_database': {
                    'status': 'ok',
                    'total_claude_sessions': len(local_sessions),
                    'imported_sessions': imported_count,
                    'live_sessions': live_count
                },
                'overall_status': 'ok'
            }
            
        except Exception as e:
            return {
                'cafed_backend': {
                    'status': 'error',
                    'error': str(e)
                },
                'local_database': {
                    'status': 'unknown'
                },
                'overall_status': 'error'
            }

    async def close(self):
        """Close resources"""
        if self.cafed_client:
            await self.cafed_client.close()


# Global sync instance for convenience
_global_sync: Optional[SessionSync] = None

def get_session_sync() -> SessionSync:
    """Get global session sync instance"""
    global _global_sync
    if _global_sync is None:
        _global_sync = SessionSync()
    return _global_sync

async def close_global_sync():
    """Close global session sync"""
    global _global_sync
    if _global_sync:
        await _global_sync.close()
        _global_sync = None

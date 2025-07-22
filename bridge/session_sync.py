"""
Session synchronization between cafed backend and Elia database
"""

import asyncio
from datetime import datetime
from typing import List, Optional
from sqlmodel import select

from bridge.cafed_client import CafedClient, ClaudeSession
from elia_chat.database.database import get_session
from elia_chat.database.models import ClaudeSessionDao, SessionIntelligenceDao


class SessionSync:
    """Synchronizes Claude Code sessions with Elia database"""
    
    def __init__(self, cafed_client: Optional[CafedClient] = None):
        self.cafed_client = cafed_client or CafedClient()
    
    async def sync_all_sessions(self) -> dict:
        """Sync all Claude Code sessions from cafed backend to Elia database"""
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
                        # Check if session already exists
                        existing = await ClaudeSessionDao.find_by_uuid(session.session_uuid)
                        
                        if existing:
                            # Update existing session
                            existing.project_name = session.project_name
                            existing.project_path = session.project_path
                            existing.status = session.status
                            existing.conversation_turns = session.conversation_turns
                            existing.total_cost_usd = session.total_cost_usd
                            existing.file_operations = session.file_operations
                            existing.jsonl_file_path = session.jsonl_file_path
                            existing.last_activity = session.last_activity
                            
                            db_session.add(existing)
                            results['updated'] += 1
                        else:
                            # Create new session
                            new_session = ClaudeSessionDao(
                                session_uuid=session.session_uuid,
                                project_name=session.project_name,
                                project_path=session.project_path,
                                status=session.status,
                                conversation_turns=session.conversation_turns,
                                total_cost_usd=session.total_cost_usd,
                                file_operations=session.file_operations,
                                jsonl_file_path=session.jsonl_file_path,
                                created_at=session.created_at,
                                last_activity=session.last_activity
                            )
                            
                            db_session.add(new_session)
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
        """Sync a specific Claude Code session"""
        try:
            # Fetch specific session from cafed backend
            session = await self.cafed_client.get_session(session_uuid)
            
            if not session:
                return False
            
            async with get_session() as db_session:
                # Check if session already exists
                existing = await ClaudeSessionDao.find_by_uuid(session_uuid)
                
                if existing:
                    # Update existing session
                    existing.project_name = session.project_name
                    existing.project_path = session.project_path
                    existing.status = session.status
                    existing.conversation_turns = session.conversation_turns
                    existing.total_cost_usd = session.total_cost_usd
                    existing.file_operations = session.file_operations
                    existing.jsonl_file_path = session.jsonl_file_path
                    existing.last_activity = session.last_activity
                    
                    db_session.add(existing)
                else:
                    # Create new session
                    new_session = ClaudeSessionDao(
                        session_uuid=session.session_uuid,
                        project_name=session.project_name,
                        project_path=session.project_path,
                        status=session.status,
                        conversation_turns=session.conversation_turns,
                        total_cost_usd=session.total_cost_usd,
                        file_operations=session.file_operations,
                        jsonl_file_path=session.jsonl_file_path,
                        created_at=session.created_at,
                        last_activity=session.last_activity
                    )
                    
                    db_session.add(new_session)
                
                await db_session.commit()
            
            return True
            
        except Exception as e:
            print(f"Failed to sync session {session_uuid}: {e}")
            return False
    
    async def get_local_sessions(self) -> List[ClaudeSessionDao]:
        """Get all Claude Code sessions from local database"""
        async with get_session() as db_session:
            statement = select(ClaudeSessionDao).order_by(ClaudeSessionDao.last_activity.desc())
            result = await db_session.exec(statement)
            return list(result)
    
    async def get_active_sessions(self) -> List[ClaudeSessionDao]:
        """Get active Claude Code sessions from local database"""
        return await ClaudeSessionDao.all_active()
    
    async def get_project_sessions(self, project_path: str) -> List[ClaudeSessionDao]:
        """Get sessions for a specific project from local database"""
        return await ClaudeSessionDao.all_by_project(project_path)
    
    async def add_intelligence(
        self,
        session_uuid: str,
        summary_type: str,
        summary_content: str,
        confidence_score: float = 1.0,
        metadata: Optional[dict] = None
    ) -> bool:
        """Add intelligence summary for a session"""
        try:
            async with get_session() as db_session:
                intelligence = SessionIntelligenceDao(
                    session_uuid=session_uuid,
                    summary_type=summary_type,
                    summary_content=summary_content,
                    confidence_score=confidence_score,
                    extra_metadata=metadata or {}
                )
                
                db_session.add(intelligence)
                await db_session.commit()
                
                # Also update the session's intelligence_summary field with the latest
                session = await ClaudeSessionDao.find_by_uuid(session_uuid)
                if session:
                    session.intelligence_summary = summary_content
                    db_session.add(session)
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
            
            # Check local database by counting sessions
            local_sessions = await self.get_local_sessions()
            
            return {
                'cafed_backend': {
                    'status': cafed_health.get('status', 'unknown'),
                    'service': cafed_health.get('service', 'unknown')
                },
                'local_database': {
                    'status': 'ok',
                    'session_count': len(local_sessions)
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

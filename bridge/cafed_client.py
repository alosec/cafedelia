"""
Python HTTP client for communicating with cafed backend
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import httpx
from dataclasses import dataclass

@dataclass
class ClaudeSession:
    """Claude Code session data structure"""
    id: str
    session_uuid: str
    project_name: str
    project_path: str
    status: str  # 'active' | 'inactive'
    created_at: datetime
    last_activity: datetime
    conversation_turns: int
    total_cost_usd: float
    file_operations: List[str]
    jsonl_file_path: str

@dataclass
class ClaudeProject:
    """Claude Code project data structure"""
    path: str
    name: str
    session_count: int
    last_activity: datetime
    sessions: List[str]  # UUIDs

@dataclass
class SessionSummary:
    """Session summary statistics"""
    total_sessions: int
    active_sessions: int
    total_projects: int
    total_cost: float

class CafedClient:
    """HTTP client for cafed backend API"""
    
    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        # Auto-detect backend URL based on environment
        if base_url is None:
            base_url = self._detect_backend_url()
        
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    def _detect_backend_url(self) -> str:
        """Detect backend URL based on environment"""
        # Check environment variable first
        env_url = os.getenv('CAFED_BACKEND_URL')
        if env_url:
            return env_url
        
        # Check if running in Docker container
        if os.path.exists('/.dockerenv'):
            # Inside container, use container name
            return "http://cafedelia-backend:8001"
        
        # Default to localhost
        port = os.getenv('CAFED_PORT', '8001')
        return f"http://localhost:{port}"
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self._client
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if cafed backend is healthy"""
        client = await self._get_client()
        try:
            response = await client.get("/health")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise ConnectionError(f"Failed to connect to cafed backend: {e}")
    
    async def get_sessions(self) -> List[ClaudeSession]:
        """Get all Claude Code sessions"""
        client = await self._get_client()
        try:
            response = await client.get("/api/sessions")
            response.raise_for_status()
            data = response.json()
            
            if not data.get('success'):
                raise RuntimeError(f"API error: {data.get('error', 'Unknown error')}")
            
            sessions = []
            for session_data in data.get('data', []):
                sessions.append(ClaudeSession(
                    id=session_data['id'],
                    session_uuid=session_data['session_uuid'],
                    project_name=session_data['project_name'],
                    project_path=session_data['project_path'],
                    status=session_data['status'],
                    created_at=datetime.fromisoformat(session_data['created_at'].replace('Z', '+00:00')),
                    last_activity=datetime.fromisoformat(session_data['last_activity'].replace('Z', '+00:00')),
                    conversation_turns=session_data['conversation_turns'],
                    total_cost_usd=session_data['total_cost_usd'],
                    file_operations=session_data['file_operations'],
                    jsonl_file_path=session_data['jsonl_file_path']
                ))
            
            return sessions
            
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to fetch sessions: {e}")
    
    async def get_session(self, session_id: str) -> Optional[ClaudeSession]:
        """Get specific Claude Code session by ID"""
        client = await self._get_client()
        try:
            response = await client.get(f"/api/sessions/{session_id}")
            
            if response.status_code == 404:
                return None
                
            response.raise_for_status()
            data = response.json()
            
            if not data.get('success'):
                raise RuntimeError(f"API error: {data.get('error', 'Unknown error')}")
            
            session_data = data['data']
            return ClaudeSession(
                id=session_data['id'],
                session_uuid=session_data['session_uuid'],
                project_name=session_data['project_name'],
                project_path=session_data['project_path'],
                status=session_data['status'],
                created_at=datetime.fromisoformat(session_data['created_at'].replace('Z', '+00:00')),
                last_activity=datetime.fromisoformat(session_data['last_activity'].replace('Z', '+00:00')),
                conversation_turns=session_data['conversation_turns'],
                total_cost_usd=session_data['total_cost_usd'],
                file_operations=session_data['file_operations'],
                jsonl_file_path=session_data['jsonl_file_path']
            )
            
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to fetch session {session_id}: {e}")
    
    async def get_projects(self) -> List[ClaudeProject]:
        """Get all Claude Code projects"""
        client = await self._get_client()
        try:
            response = await client.get("/api/projects")
            response.raise_for_status()
            data = response.json()
            
            if not data.get('success'):
                raise RuntimeError(f"API error: {data.get('error', 'Unknown error')}")
            
            projects = []
            for project_data in data.get('data', []):
                projects.append(ClaudeProject(
                    path=project_data['path'],
                    name=project_data['name'],
                    session_count=project_data['sessionCount'],
                    last_activity=datetime.fromisoformat(project_data['lastActivity'].replace('Z', '+00:00')),
                    sessions=project_data['sessions']
                ))
            
            return projects
            
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to fetch projects: {e}")
    
    async def get_summary(self) -> SessionSummary:
        """Get session summary statistics"""
        client = await self._get_client()
        try:
            response = await client.get("/api/summary")
            response.raise_for_status()
            data = response.json()
            
            if not data.get('success'):
                raise RuntimeError(f"API error: {data.get('error', 'Unknown error')}")
            
            summary_data = data['data']
            return SessionSummary(
                total_sessions=summary_data['totalSessions'],
                active_sessions=summary_data['activeSessions'],
                total_projects=summary_data['totalProjects'],
                total_cost=summary_data['totalCost']
            )
            
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to fetch summary: {e}")

    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


# Global client instance for convenience
_global_client: Optional[CafedClient] = None

def get_cafed_client() -> CafedClient:
    """Get global cafed client instance"""
    global _global_client
    if _global_client is None:
        _global_client = CafedClient()
    return _global_client

async def close_global_client():
    """Close global client"""
    global _global_client
    if _global_client:
        await _global_client.close()
        _global_client = None

"""
Add Claude Code session tracking tables

This migration adds support for tracking Claude Code sessions and their intelligence summaries.
"""

from sqlalchemy import Column, DateTime, Integer, String, Text, JSON, Float, Boolean, ForeignKey
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text


async def upgrade(engine: AsyncEngine) -> None:
    """Add Claude Code session tracking tables"""
    
    async with engine.begin() as conn:
        # Create claude_session table
        await conn.execute(text("""
            CREATE TABLE claude_session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_uuid TEXT NOT NULL UNIQUE,
                project_name TEXT NOT NULL,
                project_path TEXT NOT NULL,
                status TEXT DEFAULT 'inactive',
                conversation_turns INTEGER DEFAULT 0,
                total_cost_usd REAL DEFAULT 0.0,
                file_operations JSON DEFAULT '[]',
                jsonl_file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                intelligence_summary TEXT,
                chat_id INTEGER REFERENCES chat(id)
            )
        """))
        
        # Create index on session_uuid for fast lookups
        await conn.execute(text("""
            CREATE INDEX idx_claude_session_uuid ON claude_session(session_uuid)
        """))
        
        # Create index on status for filtering active sessions
        await conn.execute(text("""
            CREATE INDEX idx_claude_session_status ON claude_session(status)
        """))
        
        # Create index on project_path for project-based queries
        await conn.execute(text("""
            CREATE INDEX idx_claude_session_project_path ON claude_session(project_path)
        """))
        
        # Create index on last_activity for sorting
        await conn.execute(text("""
            CREATE INDEX idx_claude_session_last_activity ON claude_session(last_activity)
        """))
        
        # Create session_intelligence table
        await conn.execute(text("""
            CREATE TABLE session_intelligence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_uuid TEXT NOT NULL REFERENCES claude_session(session_uuid),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                summary_type TEXT NOT NULL,
                summary_content TEXT NOT NULL,
                confidence_score REAL DEFAULT 1.0,
                extra_metadata JSON DEFAULT '{}'
            )
        """))
        
        # Create index on session_uuid for intelligence lookups
        await conn.execute(text("""
            CREATE INDEX idx_session_intelligence_uuid ON session_intelligence(session_uuid)
        """))
        
        # Create index on timestamp for chronological ordering
        await conn.execute(text("""
            CREATE INDEX idx_session_intelligence_timestamp ON session_intelligence(timestamp)
        """))
        
        # Create index on summary_type for filtering by intelligence type
        await conn.execute(text("""
            CREATE INDEX idx_session_intelligence_type ON session_intelligence(summary_type)
        """))


async def downgrade(engine: AsyncEngine) -> None:
    """Remove Claude Code session tracking tables"""
    
    async with engine.begin() as conn:
        # Drop tables in reverse order (due to foreign key constraints)
        await conn.execute(text("DROP TABLE IF EXISTS session_intelligence"))
        await conn.execute(text("DROP TABLE IF EXISTS claude_session"))

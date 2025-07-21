"""
Claude Code CLI integration for live chat.

Uses the Claude Code CLI with structured JSON output for session management and streaming.
This provides the "Live Mode" for Cafedelia's dual-mode architecture.
Works with Claude Code subscription billing (no API key required).
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, Any
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ClaudeCodeResponse:
    """Response from Claude Code CLI."""
    content: str
    session_id: str
    metadata: Dict[str, Any]
    message_type: str  # 'user', 'assistant', 'system', 'result'
    is_complete: bool = False


class ClaudeCodeSession:
    """Wrapper for Claude Code CLI session with structured JSON output."""
    
    def __init__(self, session_id: Optional[str] = None, project_path: Optional[str] = None):
        self.session_id = session_id
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.is_active = False
        self.process: Optional[asyncio.subprocess.Process] = None
        
    async def send_message(self, message: str, resume_session: bool = False) -> AsyncGenerator[ClaudeCodeResponse, None]:
        """Send message to Claude Code CLI and yield streaming JSON responses."""
        try:
            self.is_active = True
            
            # Build Claude Code command
            cmd = ["claude", "-p", "--output-format", "stream-json"]
            
            # Add resume option if we have a session ID
            if resume_session and self.session_id:
                cmd.extend(["--resume", self.session_id])
            
            # Add the message prompt
            cmd.append(message)
            
            logger.info(f"Running Claude Code command: {' '.join(cmd[:4])} [message] (cwd: {self.project_path})")
            
            # Start the Claude Code process
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_path
            )
            
            # Read streaming JSON responses
            async for response in self._read_streaming_json():
                yield response
                
                # Stop if we get a final result
                if response.is_complete:
                    break
                        
        except Exception as e:
            logger.error(f"Error in Claude Code CLI execution: {e}")
            yield ClaudeCodeResponse(
                content=f"Error: {str(e)}",
                session_id=self.session_id or "unknown",
                metadata={"error": True},
                message_type="error",
                is_complete=True
            )
        finally:
            self.is_active = False
            if self.process:
                try:
                    self.process.terminate()
                    await self.process.wait()
                except:
                    pass
                self.process = None
    
    async def _read_streaming_json(self) -> AsyncGenerator[ClaudeCodeResponse, None]:
        """Read and parse streaming JSON output from Claude Code CLI."""
        if not self.process or not self.process.stdout:
            return
        
        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                
                line_str = line.decode('utf-8').strip()
                if not line_str:
                    continue
                
                try:
                    # Parse JSON message from Claude Code
                    message_data = json.loads(line_str)
                    response = self._parse_cli_message(message_data)
                    if response:
                        yield response
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON line: {line_str[:100]}... Error: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error reading streaming JSON: {e}")
    
    def _parse_cli_message(self, message_data: Dict[str, Any]) -> Optional[ClaudeCodeResponse]:
        """Parse CLI JSON message according to Claude Code message schema."""
        try:
            message_type = message_data.get('type', '')
            
            if message_type == "system":
                # System initialization message
                subtype = message_data.get('subtype', '')
                if subtype == "init":
                    # Update session ID from system message
                    self.session_id = message_data.get('session_id', self.session_id)
                    
                    return ClaudeCodeResponse(
                        content="Session initialized",
                        session_id=self.session_id,
                        metadata={
                            "cwd": message_data.get('cwd', str(self.project_path)),
                            "model": message_data.get('model', 'unknown'),
                            "tools": message_data.get('tools', []),
                            "mcp_servers": message_data.get('mcp_servers', []),
                            "api_key_source": message_data.get('apiKeySource', 'subscription'),
                            "permission_mode": message_data.get('permissionMode', 'default'),
                        },
                        message_type="system"
                    )
            
            elif message_type == "user":
                # User message (for context)
                content = self._extract_message_content(message_data.get('message', {}))
                
                return ClaudeCodeResponse(
                    content=content,
                    session_id=message_data.get('session_id', self.session_id),
                    metadata={},
                    message_type="user"
                )
            
            elif message_type == "assistant":
                # Assistant response message
                content = self._extract_message_content(message_data.get('message', {}))
                
                return ClaudeCodeResponse(
                    content=content,
                    session_id=message_data.get('session_id', self.session_id),
                    metadata={
                        "model": message_data.get('message', {}).get('model', 'unknown'),
                        "usage": message_data.get('message', {}).get('usage', {}),
                    },
                    message_type="assistant"
                )
            
            elif message_type == "result":
                # Final result with completion metadata
                subtype = message_data.get('subtype', 'success')
                result_content = message_data.get('result', '')
                
                # Update session ID if provided
                if 'session_id' in message_data:
                    self.session_id = message_data['session_id']
                
                return ClaudeCodeResponse(
                    content=result_content,
                    session_id=self.session_id,
                    metadata={
                        "subtype": subtype,
                        "duration_ms": message_data.get('duration_ms', 0),
                        "duration_api_ms": message_data.get('duration_api_ms', 0),
                        "total_cost_usd": message_data.get('total_cost_usd', 0),
                        "num_turns": message_data.get('num_turns', 0),
                        "is_error": message_data.get('is_error', False),
                    },
                    message_type="result",
                    is_complete=True
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing CLI message: {e}")
            return None
    
    def _extract_message_content(self, message_obj: Dict[str, Any]) -> str:
        """Extract text content from Claude Code message object."""
        content = message_obj.get('content', '')
        
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Handle content blocks (text, images, etc.)
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get('type') == 'text' and 'text' in block:
                        text_parts.append(block['text'])
                    elif 'text' in block:
                        text_parts.append(block['text'])
            return '\n'.join(text_parts)
        
        return str(content) if content else ''


class ClaudeCodeSessionManager:
    """Manager for Claude Code CLI sessions."""
    
    def __init__(self):
        self.active_sessions: Dict[str, ClaudeCodeSession] = {}
    
    async def create_session(self, project_path: Optional[str] = None) -> str:
        """Create a new Claude Code session (session ID will be generated by Claude Code CLI)."""
        session = ClaudeCodeSession(session_id=None, project_path=project_path)
        
        # We'll get the actual session ID after the first message
        temp_id = f"temp_{uuid.uuid4().hex[:8]}"
        self.active_sessions[temp_id] = session
        
        logger.info(f"Created new Claude Code session (temp ID: {temp_id})")
        return temp_id
    
    async def get_or_create_session(self, session_id: Optional[str] = None, project_path: Optional[str] = None) -> str:
        """Get existing session or create new one."""
        if session_id and session_id in self.active_sessions:
            return session_id
        
        if session_id and not session_id.startswith('temp_'):
            # This is a real Claude Code session ID - create a session object for it
            session = ClaudeCodeSession(session_id=session_id, project_path=project_path)
            self.active_sessions[session_id] = session
            logger.info(f"Prepared to resume Claude Code session: {session_id}")
            return session_id
        else:
            # Create new session
            return await self.create_session(project_path)
    
    async def send_message(self, session_id: str, message: str, resume: bool = False) -> AsyncGenerator[ClaudeCodeResponse, None]:
        """Send message to specific Claude Code session."""
        if session_id not in self.active_sessions:
            # Auto-create session if it doesn't exist
            await self.get_or_create_session(session_id)
        
        session = self.active_sessions[session_id]
        is_new_session = session.session_id is None
        
        async for response in session.send_message(message, resume_session=resume and not is_new_session):
            # Update session ID mapping when we get the real session ID
            if response.message_type == "system" and response.session_id != session_id:
                # Move session to real ID
                real_session_id = response.session_id
                if session_id.startswith('temp_') and real_session_id:
                    del self.active_sessions[session_id]
                    self.active_sessions[real_session_id] = session
                    session_id = real_session_id
                    logger.info(f"Updated session ID from temp to real: {real_session_id}")
            
            yield response
    
    def stop_session(self, session_id: str) -> None:
        """Stop a specific Claude Code session."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.is_active = False
            
            # Terminate process if running
            if session.process:
                try:
                    session.process.terminate()
                except:
                    pass
            
            del self.active_sessions[session_id]
            logger.info(f"Stopped Claude Code session: {session_id}")
    
    def stop_all_sessions(self) -> None:
        """Stop all active Claude Code sessions."""
        for session_id in list(self.active_sessions.keys()):
            self.stop_session(session_id)
        logger.info("Stopped all Claude Code sessions")
    
    def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs."""
        return [sid for sid, session in self.active_sessions.items() if session.is_active]
    
    def get_all_sessions(self) -> list[str]:
        """Get list of all session IDs."""
        return list(self.active_sessions.keys())


# Global session manager instance
session_manager = ClaudeCodeSessionManager()
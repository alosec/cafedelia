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

from .content_extractor import ContentExtractor

logger = logging.getLogger(__name__)


@dataclass
class ClaudeCodeResponse:
    """Response from Claude Code CLI."""
    content: str
    session_id: str
    metadata: Dict[str, Any]
    message_type: str  # 'user', 'assistant', 'system', 'result'
    is_complete: bool = False
    raw_message_data: Optional[Dict[str, Any]] = None  # Store raw data for rich formatting
    is_sidechain: bool = False  # Whether this is a sidechain message
    sidechain_metadata: Dict[str, Any] = None  # Sidechain execution metadata
    message_source: str = "main"  # Source: 'main', 'task', 'tool', 'todo'
    raw_json: str = ""  # Raw JSON string for atomic persistence


class ClaudeCodeSession:
    """Wrapper for Claude Code CLI session with structured JSON output."""
    
    def __init__(self, session_id: Optional[str] = None, project_path: Optional[str] = None, model: Optional[str] = None):
        self.session_id = session_id
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.model = model  # 'default', 'opus', 'sonnet'
        self.actual_model = None  # Will be set from system init response
        self.is_active = False
        self.process: Optional[asyncio.subprocess.Process] = None
        
    async def send_message(self, message: str, resume_session: bool = False) -> AsyncGenerator[ClaudeCodeResponse, None]:
        """Send message to Claude Code CLI and yield streaming JSON responses."""
        try:
            self.is_active = True
            
            # Build Claude Code command (--verbose required for stream-json)
            cmd = ["claude", "-p", "--verbose", "--output-format", "stream-json"]
            
            # Add model selection if specified
            if self.model and self.model != "default":
                cmd.extend(["--model", self.model])
                # Add fallback model for resilience
                fallback = "sonnet" if self.model == "opus" else "opus"
                cmd.extend(["--fallback-model", fallback])
            
            # Add resume option if we have a session ID
            if resume_session and self.session_id:
                cmd.extend(["--resume", self.session_id])
            
            # Add the message prompt
            cmd.append(message)
            
            logger.info(f"Running Claude Code command: {' '.join(cmd[:6])} [message] (cwd: {self.project_path})")
            
            # Start the Claude Code process with timeout
            self.process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.project_path
                ),
                timeout=10.0  # 10 second timeout for process startup
            )
            
            # Read streaming JSON responses
            async for response in self._read_streaming_json():
                yield response
                
                # Stop if we get a final result
                if response.is_complete:
                    break
                        
        except asyncio.TimeoutError:
            logger.error("Claude Code CLI process startup timeout")
            yield ClaudeCodeResponse(
                content="Error: Claude Code CLI process startup timeout",
                session_id=self.session_id or "unknown",
                metadata={"error": True, "timeout": True},
                message_type="error",
                is_complete=True
            )
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
            await self._cleanup_process()
    
    async def _cleanup_process(self) -> None:
        """Robustly clean up the subprocess."""
        if not self.process:
            return
        
        try:
            # First try graceful termination
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Force kill if it doesn't terminate gracefully
                self.process.kill()
                await self.process.wait()
        except ProcessLookupError:
            # Process already dead
            pass
        except Exception as e:
            logger.warning(f"Error cleaning up Claude Code process: {e}")
        finally:
            self.process = None
    
    async def _read_streaming_json(self) -> AsyncGenerator[ClaudeCodeResponse, None]:
        """Read and parse streaming JSON output from Claude Code CLI."""
        if not self.process or not self.process.stdout:
            return
        
        buffer = ""
        try:
            while True:
                try:
                    # Read with timeout to avoid hanging
                    line = await asyncio.wait_for(
                        self.process.stdout.readline(),
                        timeout=30.0  # 30 second timeout per line
                    )
                    
                    if not line:
                        # End of stream
                        break
                    
                    line_str = line.decode('utf-8').strip()
                    if not line_str:
                        continue
                    
                    # Add to buffer in case we get partial JSON
                    buffer += line_str
                    
                    try:
                        # Try to parse complete JSON
                        message_data = json.loads(buffer)
                        response = self._parse_cli_message(message_data, buffer)
                        if response:
                            yield response
                        buffer = ""  # Clear buffer on successful parse
                        
                    except json.JSONDecodeError:
                        # Might be partial JSON, try adding more lines
                        if len(buffer) > 10000:  # Prevent buffer overflow
                            logger.warning(f"JSON buffer too large, discarding: {buffer[:100]}...")
                            buffer = ""
                        continue
                
                except asyncio.TimeoutError:
                    logger.warning("Timeout reading from Claude Code CLI stream")
                    break
                    
        except Exception as e:
            logger.error(f"Error reading streaming JSON: {e}")
        
        # Check if there's stderr output with errors
        if self.process and self.process.stderr:
            try:
                stderr_data = await asyncio.wait_for(
                    self.process.stderr.read(1024),
                    timeout=1.0
                )
                if stderr_data:
                    stderr_str = stderr_data.decode('utf-8', errors='ignore')
                    logger.error(f"Claude Code CLI stderr: {stderr_str}")
            except:
                pass
    
    def _detect_sidechain_properties(self, message_data: Dict[str, Any]) -> tuple[bool, Dict[str, Any], str]:
        """Detect sidechain properties from message data using heuristics."""
        is_sidechain = False
        sidechain_metadata = {}
        message_source = "main"
        
        # For live streaming, we use heuristics since we don't get isSidechain flag
        raw_message = message_data.get('message', {})
        if isinstance(raw_message, dict) and 'content' in raw_message:
            content = raw_message['content']
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'tool_use':
                        tool_name = item.get('name', '')
                        # Task agent calls are typically sidechain operations
                        if tool_name == 'Task':
                            is_sidechain = True
                            message_source = "task"
                            sidechain_metadata = {
                                'tool_name': tool_name,
                                'tool_input': item.get('input', {}),
                                'detected_via': 'task_heuristic'
                            }
                        elif tool_name == 'TodoWrite':
                            is_sidechain = True
                            message_source = "todo"
                            sidechain_metadata = {
                                'tool_name': tool_name,
                                'tool_input': item.get('input', {}),
                                'detected_via': 'todo_heuristic'
                            }
                        elif tool_name in ['Agent', 'SubAgent']:
                            is_sidechain = True
                            message_source = "tool"
                            sidechain_metadata = {
                                'tool_name': tool_name,
                                'tool_input': item.get('input', {}),
                                'detected_via': 'agent_heuristic'
                            }
                        break
        
        # Add common metadata
        if is_sidechain:
            sidechain_metadata.update({
                'session_id': message_data.get('session_id'),
                'cwd': message_data.get('cwd'),
                'version': message_data.get('version'),
                'timestamp': message_data.get('timestamp')
            })
        
        return is_sidechain, sidechain_metadata, message_source
    
    def _parse_cli_message(self, message_data: Dict[str, Any], raw_json_str: str = "") -> Optional[ClaudeCodeResponse]:
        """Parse CLI JSON message according to Claude Code message schema."""
        try:
            message_type = message_data.get('type', '')
            
            # Detect sidechain properties for all message types
            is_sidechain, sidechain_metadata, message_source = self._detect_sidechain_properties(message_data)
            
            if message_type == "system":
                # System initialization message
                subtype = message_data.get('subtype', '')
                if subtype == "init":
                    # Update session ID from system message
                    self.session_id = message_data.get('session_id', self.session_id)
                    
                    # Extract and store the actual model being used
                    model_info = message_data.get('model', 'unknown')
                    self.actual_model = model_info
                    logger.info(f"Claude Code session using model: {model_info}")
                    
                    return ClaudeCodeResponse(
                        content="Session initialized",
                        session_id=self.session_id,
                        metadata={
                            "cwd": message_data.get('cwd', str(self.project_path)),
                            "model": model_info,
                            "tools": message_data.get('tools', []),
                            "mcp_servers": message_data.get('mcp_servers', []),
                            "api_key_source": message_data.get('apiKeySource', 'subscription'),
                            "permission_mode": message_data.get('permissionMode', 'default'),
                        },
                        message_type="system",
                        is_sidechain=is_sidechain,
                        sidechain_metadata=sidechain_metadata,
                        message_source=message_source,
                        raw_json=raw_json_str
                    )
            
            elif message_type == "user":
                # User message (for context)
                raw_message = message_data.get('message', {})
                # Add missing type field for ContentExtractor
                content = ContentExtractor.extract_message_content({
                    'type': 'user',
                    **raw_message
                })
                
                return ClaudeCodeResponse(
                    content=content,
                    session_id=message_data.get('session_id', self.session_id),
                    metadata={},
                    message_type="user",
                    raw_message_data={'type': 'user', **raw_message},
                    is_sidechain=is_sidechain,
                    sidechain_metadata=sidechain_metadata,
                    message_source=message_source,
                    raw_json=raw_json_str
                )
            
            elif message_type == "assistant":
                # Assistant response message
                raw_message = message_data.get('message', {})
                # Override the "type": "message" with "type": "assistant" for ContentExtractor
                corrected_message = {**raw_message, 'type': 'assistant'}
                content = ContentExtractor.extract_message_content(corrected_message)
                
                return ClaudeCodeResponse(
                    content=content,
                    session_id=message_data.get('session_id', self.session_id),
                    metadata={
                        "model": raw_message.get('model', 'unknown'),
                        "usage": raw_message.get('usage', {}),
                    },
                    message_type="assistant",
                    raw_message_data=corrected_message,
                    is_sidechain=is_sidechain,
                    sidechain_metadata=sidechain_metadata,
                    message_source=message_source,
                    raw_json=raw_json_str
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
                    is_complete=True,
                    is_sidechain=is_sidechain,
                    sidechain_metadata=sidechain_metadata,
                    message_source=message_source,
                    raw_json=raw_json_str
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing CLI message: {e}")
            return None
    
    def _extract_message_content(self, message_obj: Dict[str, Any]) -> str:
        """Extract content from Claude Code message with comprehensive tool support."""
        # Use the unified content extractor for rich tool display
        return ContentExtractor.extract_message_content(message_obj)


class ClaudeCodeSessionManager:
    """Manager for Claude Code CLI sessions."""
    
    def __init__(self):
        self.active_sessions: Dict[str, ClaudeCodeSession] = {}
    
    async def create_session(self, project_path: Optional[str] = None, model: Optional[str] = None) -> str:
        """Create a new Claude Code session (session ID will be generated by Claude Code CLI)."""
        session = ClaudeCodeSession(session_id=None, project_path=project_path, model=model)
        
        # We'll get the actual session ID after the first message
        temp_id = f"temp_{uuid.uuid4().hex[:8]}"
        self.active_sessions[temp_id] = session
        
        logger.info(f"Created new Claude Code session (temp ID: {temp_id}, model: {model})")
        return temp_id
    
    async def get_or_create_session(self, session_id: Optional[str] = None, project_path: Optional[str] = None, model: Optional[str] = None) -> str:
        """Get existing session or create new one."""
        if session_id and session_id in self.active_sessions:
            return session_id
        
        if session_id and not session_id.startswith('temp_'):
            # This is a real Claude Code session ID - create a session object for it
            session = ClaudeCodeSession(session_id=session_id, project_path=project_path, model=model)
            self.active_sessions[session_id] = session
            logger.info(f"Prepared to resume Claude Code session: {session_id}")
            return session_id
        else:
            # Create new session
            return await self.create_session(project_path, model)
    
    async def send_message(self, session_id: str, message: str, resume: bool = False, model: Optional[str] = None) -> AsyncGenerator[ClaudeCodeResponse, None]:
        """Send message to specific Claude Code session."""
        if session_id not in self.active_sessions:
            # Auto-create session if it doesn't exist
            await self.get_or_create_session(session_id, model=model)
        
        session = self.active_sessions[session_id]
        is_new_session = session.session_id is None
        
        # Update model if provided and session is new
        if model and is_new_session:
            session.model = model
        
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
    
    async def stop_session(self, session_id: str) -> None:
        """Stop a specific Claude Code session."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.is_active = False
            
            # Use robust cleanup
            await session._cleanup_process()
            
            del self.active_sessions[session_id]
            logger.info(f"Stopped Claude Code session: {session_id}")
    
    async def stop_all_sessions(self) -> None:
        """Stop all active Claude Code sessions."""
        for session_id in list(self.active_sessions.keys()):
            await self.stop_session(session_id)
        logger.info("Stopped all Claude Code sessions")
    
    def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs."""
        return [sid for sid, session in self.active_sessions.items() if session.is_active]
    
    def get_all_sessions(self) -> list[str]:
        """Get list of all session IDs."""
        return list(self.active_sessions.keys())


# Global session manager instance
session_manager = ClaudeCodeSessionManager()
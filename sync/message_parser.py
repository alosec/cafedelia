"""
Individual message parsing from Claude Code JSON streams.

Handles atomic parsing of each JSON message with sidechain detection,
metadata extraction, and proper typing for immediate database storage.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ParsedMessage:
    """Parsed message ready for database storage."""
    session_id: str
    message_type: str  # 'user', 'assistant', 'system', 'result'
    content: str
    raw_json: str
    message_metadata: Dict[str, Any]
    timestamp: datetime
    
    # Sidechain properties
    is_sidechain: bool = False
    sidechain_metadata: Dict[str, Any] = None
    message_source: str = "main"  # 'main', 'task', 'tool', 'todo'
    
    def __post_init__(self):
        if self.sidechain_metadata is None:
            self.sidechain_metadata = {}


class MessageParser:
    """Parse individual Claude Code JSON messages for atomic database storage."""
    
    def __init__(self):
        # Track message ordering for proper sequence
        self.message_sequence = 0
    
    def parse_claude_message(self, raw_json_str: str, session_id_override: Optional[str] = None) -> Optional[ParsedMessage]:
        """
        Parse a single Claude Code JSON message into ParsedMessage format.
        
        Args:
            raw_json_str: Raw JSON string from Claude Code stream
            
        Returns:
            ParsedMessage ready for database storage, or None if parsing fails
        """
        try:
            import json
            message_data = json.loads(raw_json_str)
            
            # Increment sequence for ordering
            self.message_sequence += 1
            
            # Extract basic message properties
            message_type = message_data.get('type', '')
            session_id = session_id_override or message_data.get('session_id', '')
            timestamp = self._extract_timestamp(message_data)
            
            # Detect sidechain properties
            is_sidechain, sidechain_metadata, message_source = self._detect_sidechain_properties(message_data)
            
            # Extract content based on message type
            content = self._extract_content(message_data, message_type)
            
            # Build metadata with datetime serialization
            message_metadata = self._extract_metadata(message_data, message_type)
            message_metadata['sequence'] = self.message_sequence
            
            # Ensure datetime objects are serialized
            from datetime import datetime
            def serialize_datetime_in_metadata(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: serialize_datetime_in_metadata(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [serialize_datetime_in_metadata(item) for item in obj]
                return obj
            
            message_metadata = serialize_datetime_in_metadata(message_metadata)
            sidechain_metadata = serialize_datetime_in_metadata(sidechain_metadata)
            
            return ParsedMessage(
                session_id=session_id,
                message_type=message_type,
                content=content,
                raw_json=raw_json_str,
                message_metadata=message_metadata,
                timestamp=timestamp,
                is_sidechain=is_sidechain,
                sidechain_metadata=sidechain_metadata,
                message_source=message_source
            )
            
        except Exception as e:
            logger.error(f"Failed to parse Claude Code message: {e}")
            logger.debug(f"Raw JSON: {raw_json_str[:200]}...")
            return None
    
    def _extract_timestamp(self, message_data: Dict[str, Any]) -> datetime:
        """Extract timestamp from message data."""
        timestamp_str = message_data.get('timestamp')
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except:
                pass
        return datetime.utcnow()
    
    def _detect_sidechain_properties(self, message_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
        """Detect sidechain properties from message data."""
        is_sidechain = False
        sidechain_metadata = {}
        message_source = "main"
        
        # Check for explicit isSidechain flag (from JSONL files)
        if message_data.get('isSidechain'):
            is_sidechain = True
            sidechain_metadata = {
                'userType': message_data.get('userType'),
                'parentUuid': message_data.get('parentUuid'),
                'cwd': message_data.get('cwd'),
                'gitBranch': message_data.get('gitBranch'),
                'detected_via': 'explicit_flag'
            }
            
            # Determine message source from userType
            user_type = message_data.get('userType', '')
            if 'task' in user_type.lower():
                message_source = "task"
            elif 'todo' in user_type.lower():
                message_source = "todo"
            else:
                message_source = "tool"
        
        else:
            # Heuristic detection for live streaming
            raw_message = message_data.get('message', {})
            if isinstance(raw_message, dict) and 'content' in raw_message:
                content = raw_message['content']
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_use':
                            tool_name = item.get('name', '')
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
                            
                            if is_sidechain:
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
    
    def _extract_content(self, message_data: Dict[str, Any], message_type: str) -> str:
        """Extract content from message data based on type."""
        if message_type == "system":
            subtype = message_data.get('subtype', '')
            if subtype == "init":
                model = message_data.get('model', 'unknown')
                tools = len(message_data.get('tools', []))
                return f"Session initialized (model: {model}, tools: {tools})"
            return message_data.get('content', 'System message')
        
        elif message_type == "user":
            # Handle both JSONL and streaming formats
            raw_message = message_data.get('message', {})
            
            # Check for tool results in JSONL format
            if 'toolUseResult' in message_data:
                tool_result = message_data['toolUseResult']
                tool_name = tool_result.get('toolName', 'unknown')
                result_text = tool_result.get('result', '')
                return f"Tool Result ({tool_name}): {result_text}"
            
            # Handle streaming/message format
            content = raw_message.get('content', '')
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                return '\n'.join(text_parts) if text_parts else ''
            
            return str(content) if content else ''
        
        elif message_type == "assistant":
            raw_message = message_data.get('message', {})
            content = raw_message.get('content', '')
            
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Extract text and tool use information
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        item_type = item.get('type', '')
                        if item_type == 'text':
                            text = item.get('text', '').strip()
                            if text:
                                parts.append(text)
                        elif item_type == 'tool_use':
                            tool_name = item.get('name', 'unknown')
                            tool_id = item.get('id', '')[:8] + '...' if item.get('id') else ''
                            parts.append(f"[Tool Use: {tool_name} ({tool_id})]")
                
                return '\n'.join(parts) if parts else ''
            
            return str(content) if content else ''
        
        elif message_type == "result":
            result_content = message_data.get('result', '')
            subtype = message_data.get('subtype', 'success')
            duration = message_data.get('duration_ms', 0)
            return f"Result ({subtype}): {result_content} (took {duration}ms)"
        
        # Fallback
        return message_data.get('content', str(message_data.get('message', '')))
    
    def _extract_metadata(self, message_data: Dict[str, Any], message_type: str) -> Dict[str, Any]:
        """Extract metadata from message data."""
        metadata = {}
        
        # Common metadata
        if 'cwd' in message_data:
            metadata['cwd'] = message_data['cwd']
        if 'version' in message_data:
            metadata['version'] = message_data['version']
        if 'gitBranch' in message_data:
            metadata['git_branch'] = message_data['gitBranch']
        
        # Type-specific metadata
        if message_type == "system":
            metadata.update({
                'subtype': message_data.get('subtype'),
                'model': message_data.get('model'),
                'tools': message_data.get('tools', []),
                'mcp_servers': message_data.get('mcp_servers', []),
                'api_key_source': message_data.get('apiKeySource'),
                'permission_mode': message_data.get('permissionMode')
            })
        
        elif message_type == "assistant":
            raw_message = message_data.get('message', {})
            metadata.update({
                'model': raw_message.get('model'),
                'usage': raw_message.get('usage', {}),
                'stop_reason': raw_message.get('stop_reason')
            })
        
        elif message_type == "user" and 'toolUseResult' in message_data:
            tool_result = message_data['toolUseResult']
            metadata.update({
                'tool_name': tool_result.get('toolName'),
                'tool_use_id': tool_result.get('toolUseId'),
                'duration_ms': tool_result.get('durationMs'),
                'url': tool_result.get('url'),
                'is_error': tool_result.get('isError', False)
            })
        
        elif message_type == "result":
            metadata.update({
                'subtype': message_data.get('subtype'),
                'duration_ms': message_data.get('duration_ms'),
                'duration_api_ms': message_data.get('duration_api_ms'),
                'total_cost_usd': message_data.get('total_cost_usd'),
                'num_turns': message_data.get('num_turns'),
                'is_error': message_data.get('is_error', False)
            })
        
        # Clean up None values
        return {k: v for k, v in metadata.items() if v is not None}
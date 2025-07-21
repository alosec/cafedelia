"""
Shared content extraction logic for Claude Code responses.

Unifies content parsing between live streaming and historical processing to ensure
consistent tool use display across both modes.
"""

from typing import List, Dict, Any


class ContentExtractor:
    """Unified content extraction for Claude Code messages."""
    
    # Aggressive content limits for database storage
    MAX_TOOL_RESULT_LENGTH = 500  # Reduced from 1000
    MAX_TEXT_LENGTH = 2000  # Limit for assistant reasoning text
    MAX_PARAM_LENGTH = 50  # Reduced from 100
    MAX_PARAMS_SHOWN = 2  # Reduced from 3
    
    # Tools that produce massive outputs
    VERBOSE_TOOLS = {'LS', 'Grep', 'Glob', 'find', 'tree', 'cat', 'head', 'tail'}
    VERBOSE_TOOL_MAX_LENGTH = 200  # Even more aggressive for known verbose tools
    
    @staticmethod
    def extract_assistant_content(message_data: Dict[str, Any]) -> List[str]:
        """Extract content from assistant message, including reasoning and tool calls."""
        content_parts = []
        
        # Handle different message structures (live streaming vs JSONL)
        content = None
        if 'message' in message_data and 'content' in message_data['message']:
            content = message_data['message']['content']
        elif 'content' in message_data:
            content = message_data['content']
        
        if not content:
            return content_parts
            
        if isinstance(content, list):
            text_parts = []
            tool_parts = []
            
            for item in content:
                if isinstance(item, dict):
                    item_type = item.get('type', '')
                    if item_type == 'text':
                        text = item.get('text', '').strip()
                        if text:
                            # Limit text length for database storage
                            if len(text) > ContentExtractor.MAX_TEXT_LENGTH:
                                text = text[:ContentExtractor.MAX_TEXT_LENGTH] + "..."
                            text_parts.append(text)
                    elif item_type == 'tool_use':
                        tool_name = item.get('name', 'unknown')
                        tool_input = item.get('input', {})
                        tool_id = item.get('id', '')[:8] + '...' if item.get('id') else ''
                        
                        # Format tool call nicely
                        tool_desc = f"🔧 **Used {tool_name}** (`{tool_id}`)"
                        if tool_input:
                            # Show key parameters (truncated for readability)
                            key_params = []
                            for key, value in list(tool_input.items())[:ContentExtractor.MAX_PARAMS_SHOWN]:
                                if isinstance(value, str) and len(value) > ContentExtractor.MAX_PARAM_LENGTH:
                                    value = value[:ContentExtractor.MAX_PARAM_LENGTH] + "..."
                                elif isinstance(value, (list, dict)):
                                    value = f"[{type(value).__name__}]"  # Just show type for complex objects
                                key_params.append(f"{key}: {value}")
                            if key_params:
                                tool_desc += f"\n  Parameters: {', '.join(key_params)}"
                        tool_parts.append(tool_desc)
            
            # Combine text and tool parts
            if text_parts:
                content_parts.extend(text_parts)
            if tool_parts:
                content_parts.extend(tool_parts)
        
        elif isinstance(content, str):
            content_parts.append(content)
        
        return content_parts
    
    @staticmethod
    def extract_tool_result_content(message_data: Dict[str, Any]) -> List[str]:
        """Extract and format tool result content."""
        content_parts = []
        
        # Handle JSONL format tool results
        if 'toolUseResult' in message_data:
            tool_result = message_data['toolUseResult']
            result_text = tool_result.get('result', '')
            tool_name = tool_result.get('toolName', '')
            
            if result_text:
                # Check if this is a verbose tool
                max_length = ContentExtractor.MAX_TOOL_RESULT_LENGTH
                if tool_name in ContentExtractor.VERBOSE_TOOLS:
                    max_length = ContentExtractor.VERBOSE_TOOL_MAX_LENGTH
                
                # Aggressively truncate results for database storage
                if len(result_text) > max_length:
                    # For verbose tools, show just a summary
                    if tool_name in ContentExtractor.VERBOSE_TOOLS:
                        lines = result_text.split('\n')
                        summary = f"[{tool_name} output: {len(lines)} lines, {len(result_text)} chars]"
                        result_text = summary + f"\n{lines[0] if lines else ''}...\n[truncated]"
                    else:
                        result_text = result_text[:max_length] + "\n[... truncated ...]"
                
                result_part = f"📋 **Tool Result:**\n```\n{result_text}\n```"
                
                # Add metadata if available
                if 'url' in tool_result:
                    result_part += f"\n*Source: {tool_result['url']}*"
                if 'durationMs' in tool_result:
                    duration = tool_result['durationMs']
                    result_part += f" *({duration}ms)*"
                
                content_parts.append(result_part)
        
        # Handle streaming format tool results in message content
        content = None
        if 'message' in message_data and 'content' in message_data['message']:
            content = message_data['message']['content']
        elif 'content' in message_data:
            content = message_data['content']
            
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'tool_result':
                    result_content = item.get('content', '')
                    if result_content:
                        if len(result_content) > ContentExtractor.MAX_TOOL_RESULT_LENGTH:
                            result_content = result_content[:ContentExtractor.MAX_TOOL_RESULT_LENGTH] + "\n[... truncated ...]"
                        content_parts.append(f"📋 **Tool Result:**\n```\n{result_content}\n```")
        
        return content_parts
    
    @staticmethod
    def extract_message_content(message_data: Dict[str, Any]) -> str:
        """
        Universal content extraction that handles all message types with tool support.
        
        This replaces the simplified extraction in claude_process.py with comprehensive
        parsing that matches the rich display of historical chat.
        """
        content_parts = []
        
        # Get message type
        msg_type = message_data.get('type', '')
        
        if msg_type == 'assistant':
            content_parts.extend(ContentExtractor.extract_assistant_content(message_data))
        elif msg_type == 'user':
            # Check for tool results first
            tool_results = ContentExtractor.extract_tool_result_content(message_data)
            if tool_results:
                content_parts.extend(tool_results)
            else:
                # Extract regular user content
                content = None
                if 'message' in message_data and 'content' in message_data['message']:
                    content = message_data['message']['content']
                elif 'content' in message_data:
                    content = message_data['content']
                
                if isinstance(content, str):
                    content_parts.append(content)
                elif isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text = item.get('text', '').strip()
                            if text:
                                text_parts.append(text)
                    content_parts.extend(text_parts)
        else:
            # Fallback for other message types
            content = message_data.get('content', '')
            if isinstance(content, str):
                content_parts.append(content)
            elif isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text = item.get('text', '').strip()
                        if text:
                            text_parts.append(text)
                content_parts.extend(text_parts)
        
        return '\n'.join(content_parts) if content_parts else ''
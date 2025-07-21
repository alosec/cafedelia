"""
Shared content extraction logic for Claude Code responses.

Unifies content parsing between live streaming and historical processing to ensure
consistent tool use display across both modes.
"""

from typing import List, Dict, Any


class ContentExtractor:
    """Unified content extraction for Claude Code messages."""
    
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
                            for key, value in tool_input.items():
                                if isinstance(value, str) and len(value) > 100:
                                    value = value[:100] + "..."
                                key_params.append(f"{key}: {value}")
                            if key_params:
                                tool_desc += f"\n  Parameters: {', '.join(key_params[:3])}"
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
            
            if result_text:
                # Truncate very long results but show more than before
                if len(result_text) > 1000:
                    result_text = result_text[:1000] + "\n\n[... truncated ...]"
                
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
                        if len(result_content) > 1000:
                            result_content = result_content[:1000] + "\n\n[... truncated ...]"
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
#!/usr/bin/env python3
"""
Detailed debug of content extraction to understand tool result parsing issues.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from sync.content_extractor import ContentExtractor

# Mock responses from the debug output
assistant_response_2 = {
    'id': 'msg_01QEQhk8gJVKWBpgaKECDm7x',
    'type': 'assistant',
    'role': 'assistant',
    'model': 'claude-sonnet-4-20250514',
    'content': [
        {
            'type': 'tool_use',
            'id': 'toolu_01Y2TZvxgZmFmYFBZqPNZjbz',
            'name': 'Bash',
            'input': {
                'command': 'ls -la',
                'description': 'List files in current directory'
            }
        }
    ],
    'stop_reason': 'tool_use',
    'stop_sequence': None,
    'usage': {
        'input_tokens': 4,
        'cache_creation_input_tokens': 6014,
        'cache_read_input_tokens': 10367,
        'output_tokens': 73,
        'service_tier': 'standard'
    }
}

user_response_3 = {
    'role': 'user',
    'content': [
        {
            'type': 'tool_result',
            'tool_use_id': 'toolu_01Y2TZvxgZmFmYFBZqPNZjbz',
            'content': 'CLAUDE_CODE_JSONL_ANALYSIS.md\nCLAUDE.md\ndebug_streaming.py\nelia_chat\nLICENSE\nmemory-bank\npyproject.toml\nREADM'
        }
    ]
}

print("=== Content Extraction Debug ===")

print("\n1. Assistant response with tool_use:")
print(f"Raw content: {json.dumps(assistant_response_2, indent=2)[:500]}...")

extracted_assistant = ContentExtractor.extract_message_content({
    'type': 'assistant',
    'message': assistant_response_2
})
print(f"Extracted: '{extracted_assistant}'")

print("\n2. User response with tool_result:")
print(f"Raw content: {json.dumps(user_response_3, indent=2)}")

extracted_user = ContentExtractor.extract_message_content({
    'type': 'user', 
    'message': user_response_3
})
print(f"Extracted: '{extracted_user}'")

print("\n3. Direct content extraction from assistant:")
assistant_content = ContentExtractor.extract_assistant_content({
    'content': assistant_response_2['content']
})
print(f"Assistant content parts: {assistant_content}")

print("\n4. Direct content extraction from tool result:")
tool_result_content = ContentExtractor.extract_tool_result_content({
    'content': user_response_3['content']
})
print(f"Tool result content parts: {tool_result_content}")

print("\n5. Testing with direct format (no message wrapper):")
extracted_direct_assistant = ContentExtractor.extract_message_content({
    'type': 'assistant',
    'content': assistant_response_2['content']
})
print(f"Direct assistant extracted: '{extracted_direct_assistant}'")

extracted_direct_user = ContentExtractor.extract_message_content({
    'type': 'user',
    'content': user_response_3['content'] 
})
print(f"Direct user extracted: '{extracted_direct_user}'")
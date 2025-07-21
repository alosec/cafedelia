#!/usr/bin/env python3
"""
Trace the exact issue with content extraction in the streaming pipeline.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from sync.content_extractor import ContentExtractor

# Simulating what happens in the streaming pipeline

print("=== Tracing Content Extraction Issue ===")

# This is what raw_message_data looks like for assistant tool use response
assistant_raw_message = {
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

# This is what raw_message_data looks like for user tool result response
user_raw_message = {
    'role': 'user',
    'content': [
        {
            'type': 'tool_result',
            'tool_use_id': 'toolu_01Y2TZvxgZmFmYFBZqPNZjbz',
            'content': 'CLAUDE_CODE_JSONL_ANALYSIS.md\nCLAUDE.md\ndebug_streaming.py\nelia_chat\nLICENSE\nmemory-bank\npyproject.toml\nREADME.md\nsync\ntest_pagination.py\ntests\nTRANSFORMATION_IMPLEMENTATION.md\nuv.lock'
        }
    ]
}

print("\n1. Testing streaming grouper logic for assistant:")
# This is what the streaming grouper does:
formatted_data = {
    'type': 'assistant',
    **assistant_raw_message
}
print(f"Formatted data keys: {list(formatted_data.keys())}")
print(f"Formatted data type: {formatted_data.get('type')}")

extracted = ContentExtractor.extract_message_content(formatted_data)
print(f"Assistant extracted: '{extracted}'")

print("\n2. Testing streaming grouper logic for user tool result:")
formatted_data_user = {
    'type': 'user',
    **user_raw_message  
}
print(f"Formatted data keys: {list(formatted_data_user.keys())}")
print(f"Formatted data type: {formatted_data_user.get('type')}")

extracted_user = ContentExtractor.extract_message_content(formatted_data_user)
print(f"User extracted: '{extracted_user}'")

print("\n3. Checking content structure match:")
print("Assistant content structure:")
print(f"  Has 'content': {'content' in formatted_data}")
print(f"  Content type: {type(formatted_data.get('content'))}")
print(f"  Content[0] type: {formatted_data['content'][0].get('type') if formatted_data.get('content') else 'N/A'}")

print("\nUser content structure:")
print(f"  Has 'content': {'content' in formatted_data_user}")
print(f"  Content type: {type(formatted_data_user.get('content'))}")
print(f"  Content[0] type: {formatted_data_user['content'][0].get('type') if formatted_data_user.get('content') else 'N/A'}")

print("\n4. Testing ContentExtractor methods directly:")
print("extract_assistant_content:")
assistant_parts = ContentExtractor.extract_assistant_content(formatted_data)
print(f"  Result: {assistant_parts}")

print("extract_tool_result_content:")
tool_parts = ContentExtractor.extract_tool_result_content(formatted_data_user)
print(f"  Result: {tool_parts}")

print("\n5. Testing why content might be empty:")
# Check if the extraction is actually returning empty string due to some path issue

# Let's trace the extraction path step by step
def trace_extract_message_content(message_data):
    print(f"  Input type: {message_data.get('type')}")
    msg_type = message_data.get('type', '')
    
    if msg_type == 'assistant':
        print("  -> Taking assistant path")
        return ContentExtractor.extract_assistant_content(message_data)
    elif msg_type == 'user':
        print("  -> Taking user path")
        tool_results = ContentExtractor.extract_tool_result_content(message_data)
        if tool_results:
            print(f"  -> Found tool results: {len(tool_results)} items")
            return tool_results
        else:
            print("  -> No tool results, extracting regular content")
            # Regular content path...
            content = None
            if 'message' in message_data and 'content' in message_data['message']:
                content = message_data['message']['content']
            elif 'content' in message_data:
                content = message_data['content']
            
            print(f"  -> Content for regular extraction: {type(content)}")
            return []

print("\nTracing assistant extraction:")
result_assistant = trace_extract_message_content(formatted_data)
print(f"Final result: {result_assistant}")

print("\nTracing user extraction:")
result_user = trace_extract_message_content(formatted_data_user)
print(f"Final result: {result_user}")
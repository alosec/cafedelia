#!/usr/bin/env python3
"""
Debug the exact parsing issue in claude_process.py _parse_cli_message method.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from sync.content_extractor import ContentExtractor

# Simulate what happens in _parse_cli_message for assistant tool use
message_data = {
    'type': 'assistant',
    'session_id': 'some-session-id',
    'message': {
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
}

print("=== Debug Parsing Issue ===")

print("1. What claude_process.py does:")
raw_message = message_data.get('message', {})
print(f"raw_message keys: {list(raw_message.keys())}")
print(f"raw_message type field: {raw_message.get('type')}")

print("\n2. Calling ContentExtractor.extract_message_content(raw_message):")
content = ContentExtractor.extract_message_content(raw_message)
print(f"Result: '{content}'")

print("\n3. The issue - raw_message is missing the top-level type!")
print("ContentExtractor expects format like:")
print("  {'type': 'assistant', 'content': [...], ...}")
print("But gets:")
print("  {'id': '...', 'type': 'assistant', 'content': [...], ...}")

print("\n4. What it should be doing:")
correct_format = {
    'type': 'assistant',
    **raw_message
}
correct_content = ContentExtractor.extract_message_content(correct_format)
print(f"Correct result: '{correct_content}'")

print("\n5. For user tool result:")
user_message_data = {
    'type': 'user',
    'session_id': 'some-session-id',
    'message': {
        'role': 'user',
        'content': [
            {
                'type': 'tool_result',
                'tool_use_id': 'toolu_01Y2TZvxgZmFmYFBZqPNZjbz',
                'content': 'ls output here...'
            }
        ]
    }
}

user_raw_message = user_message_data.get('message', {})
print(f"User raw_message keys: {list(user_raw_message.keys())}")
user_content = ContentExtractor.extract_message_content(user_raw_message)
print(f"User result: '{user_content}'")

user_correct_format = {
    'type': 'user',
    **user_raw_message
}
user_correct_content = ContentExtractor.extract_message_content(user_correct_format)
print(f"User correct result: '{user_correct_content}'")
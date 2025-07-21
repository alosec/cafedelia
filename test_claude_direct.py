#!/usr/bin/env python3
"""
Direct Claude Code testing script for debugging tool use and streaming.

This bypasses the TUI to test the core Claude Code integration directly,
showing raw responses and formatted output side by side.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sync.claude_process import ClaudeCodeSession
from sync.streaming_message_grouper import StreamingMessageGrouper
from sync.content_extractor import ContentExtractor


async def test_claude_direct(prompt: str = "List the files in the current directory using ls"):
    """Test Claude Code integration with real-time output."""
    
    print("🧪 Testing Claude Code Direct Integration")
    print("=" * 60)
    print(f"Prompt: {prompt}")
    print()
    
    # Create Claude Code session
    session = ClaudeCodeSession()
    grouper = StreamingMessageGrouper()
    
    print("📡 Raw Claude Code Responses:")
    print("-" * 40)
    
    try:
        async for response in session.send_message(prompt):
            # Show raw response structure
            print(f"🔍 RAW: type={response.message_type}")
            if response.raw_message_data:
                print(f"   Raw data keys: {list(response.raw_message_data.keys())}")
                if 'content' in response.raw_message_data:
                    content = response.raw_message_data['content']
                    if isinstance(content, list):
                        for i, item in enumerate(content):
                            if isinstance(item, dict):
                                print(f"   Content[{i}]: type={item.get('type', 'unknown')}")
                                if item.get('type') == 'tool_use':
                                    print(f"      Tool: {item.get('name', 'unknown')}")
                                    print(f"      ID: {item.get('id', 'unknown')[:12]}...")
                                    print(f"      Input: {item.get('input', {})}")
                    else:
                        print(f"   Content: {str(content)[:100]}...")
            
            # Test ContentExtractor directly on this raw data
            if response.raw_message_data:
                print(f"   📝 Raw message data structure:")
                import json
                print(f"      {json.dumps(response.raw_message_data, indent=6)[:500]}...")
                print(f"   📝 Direct ContentExtractor test:")
                direct_result = ContentExtractor.extract_message_content(response.raw_message_data)
                print(f"      Result: {repr(direct_result[:200])}")
                print(f"      Has tool emoji: {'🔧' in direct_result}")
            
            print(f"   🏭 Processed content: {response.content[:200]}")
            if len(response.content) > 200:
                print(f"      [Content truncated, full length: {len(response.content)} chars]")
            print()
            
            # Process through message grouper
            grouped_message = grouper.add_response(response)
            
            if grouped_message:
                print("✨ FORMATTED MESSAGE GROUP:")
                print("-" * 40)
                print(grouped_message.content)
                print()
                print(f"Has tool emoji: {'🔧' in grouped_message.content}")
                print(f"Has result emoji: {'📋' in grouped_message.content}")
                print("-" * 40)
                print()
            
            # Handle completion
            if response.is_complete:
                # Force complete any remaining group
                final_group = grouper.force_complete_group()
                if final_group:
                    print("🏁 FINAL GROUP:")
                    print("-" * 40)
                    print(final_group.content)
                    print()
                break
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("✅ Test completed")


async def test_content_extractor_directly():
    """Test ContentExtractor with mock Claude Code data."""
    
    print("\n🧪 Testing ContentExtractor Directly")
    print("=" * 60)
    
    # Mock assistant message with tool use (Claude Code format)
    mock_assistant = {
        'type': 'assistant',
        'content': [
            {
                'type': 'text',
                'text': 'I\'ll help you list the files in the current directory.'
            },
            {
                'type': 'tool_use',
                'id': 'toolu_123456789abcdef',
                'name': 'Bash',
                'input': {
                    'command': 'ls -la'
                }
            }
        ]
    }
    
    # Mock user message with tool result
    mock_user = {
        'type': 'user',
        'content': [
            {
                'type': 'tool_result',
                'tool_use_id': 'toolu_123456789abcdef',
                'content': 'total 48\ndrwxr-xr-x 8 alex alex 4096 Jul 21 15:30 .\ndrwxr-xr-x 3 alex alex 4096 Jul 20 10:15 ..\n-rw-r--r-- 1 alex alex 1234 Jul 21 15:30 test_claude_direct.py'
            }
        ]
    }
    
    print("📝 Extracting assistant content:")
    assistant_formatted = ContentExtractor.extract_message_content(mock_assistant)
    print(assistant_formatted)
    print()
    
    print("📝 Extracting user tool result:")
    user_formatted = ContentExtractor.extract_message_content(mock_user)
    print(user_formatted)
    print()
    
    print("✨ Combined conversation:")
    print("-" * 40)
    print(assistant_formatted)
    if user_formatted:
        print()
        print(user_formatted)
    print("-" * 40)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Claude Code integration directly")
    parser.add_argument(
        "--prompt", 
        "-p", 
        default="List the files in the current directory using ls",
        help="Prompt to send to Claude Code"
    )
    parser.add_argument(
        "--test-extractor",
        "-e", 
        action="store_true",
        help="Test ContentExtractor with mock data instead of live Claude"
    )
    
    args = parser.parse_args()
    
    if args.test_extractor:
        asyncio.run(test_content_extractor_directly())
    else:
        asyncio.run(test_claude_direct(args.prompt))
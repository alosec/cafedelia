#!/usr/bin/env python3
"""
Debug script to test Claude Code streaming and identify tool result issues.
This will help us understand exactly where in the pipeline tool results are being lost.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from sync.claude_process import ClaudeCodeSession
from sync.streaming_message_grouper import StreamingMessageGrouper
from sync.content_extractor import ContentExtractor

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_streaming_flow():
    """Test the complete streaming flow to identify where tool results are lost."""
    
    print("=== Claude Code Streaming Debug Test ===")
    
    # Test message that should trigger tool use
    test_message = "List the files in the current directory using the ls command"
    
    session = ClaudeCodeSession(project_path=str(Path.cwd()))
    grouper = StreamingMessageGrouper()
    
    print(f"\n1. Sending message: {test_message}")
    
    message_count = 0
    responses = []
    
    try:
        async for response in session.send_message(test_message, resume_session=False):
            message_count += 1
            responses.append(response)
            
            print(f"\n--- Response {message_count} ---")
            print(f"Type: {response.message_type}")
            print(f"Content: {response.content[:200]}{'...' if len(response.content) > 200 else ''}")
            print(f"Is Complete: {response.is_complete}")
            print(f"Metadata: {response.metadata}")
            
            if response.raw_message_data:
                print(f"Raw Message Data Keys: {list(response.raw_message_data.keys())}")
                
                # Check if raw data contains tool information
                if 'content' in response.raw_message_data:
                    content = response.raw_message_data['content']
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                print(f"  Content item type: {item.get('type', 'unknown')}")
                                if item.get('type') == 'tool_use':
                                    print(f"    Tool: {item.get('name')} ID: {item.get('id', '')[:8]}...")
                                elif item.get('type') == 'tool_result':
                                    print(f"    Tool result for: {item.get('tool_use_id', '')[:8]}...")
            
            # Test the grouper
            grouped = grouper.add_response(response)
            if grouped:
                print(f"\n>>> GROUPED MESSAGE READY:")
                print(f"Type: {grouped.message_type}")
                print(f"Content: {grouped.content[:300]}{'...' if len(grouped.content) > 300 else ''}")
                print(f"Metadata: {grouped.metadata}")
            
            # Check content extraction
            if response.raw_message_data:
                extracted = ContentExtractor.extract_message_content(response.raw_message_data)
                print(f"\nExtracted Content: {extracted[:200]}{'...' if len(extracted) > 200 else ''}")
            
            if response.is_complete:
                print("\n=== STREAM COMPLETE ===")
                break
    
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nTotal responses: {message_count}")
    
    # Force complete any remaining group
    final_group = grouper.force_complete_group()
    if final_group:
        print(f"\nFinal forced group:")
        print(f"Content: {final_group.content}")
        print(f"Metadata: {final_group.metadata}")
    
    # Analyze response types
    response_types = {}
    for resp in responses:
        resp_type = resp.message_type
        response_types[resp_type] = response_types.get(resp_type, 0) + 1
    
    print(f"\nResponse type summary: {response_types}")
    
    # Check for tool-related responses
    tool_responses = [r for r in responses if 'tool' in r.content.lower() or 
                     (r.raw_message_data and 'tool' in str(r.raw_message_data).lower())]
    
    print(f"\nTool-related responses: {len(tool_responses)}")
    for i, tool_resp in enumerate(tool_responses):
        print(f"  {i+1}. Type: {tool_resp.message_type}, Content snippet: {tool_resp.content[:100]}...")

if __name__ == "__main__":
    asyncio.run(test_streaming_flow())
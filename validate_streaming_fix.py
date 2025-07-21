#!/usr/bin/env python3
"""
Simple validation script to test the streaming message grouper fix.
"""

import sys
from pathlib import Path

# Add the sync module to path
sys.path.insert(0, str(Path(__file__).parent / "sync"))

from streaming_message_grouper import StreamingMessageGrouper
from claude_process import ClaudeCodeResponse

def test_grouper_completion():
    """Test that the force_complete_group method works."""
    print("🧪 Testing StreamingMessageGrouper force completion...")
    
    grouper = StreamingMessageGrouper()
    
    # Simulate a typical Task agent response
    mock_assistant_response = ClaudeCodeResponse(
        message_type="assistant",
        content='{"type": "tool_use", "name": "Task", "input": {"description": "Test", "prompt": "This is a comprehensive test"}}',
        is_complete=False,
        session_id="test-session",
        metadata={"tokens": 100}
    )
    
    # Add the response to grouper
    result1 = grouper.add_response(mock_assistant_response)
    print(f"Initial response processing: {result1 is not None}")
    
    # Test force completion
    forced_result = grouper.force_complete_group()
    print(f"Force completion returned content: {forced_result is not None}")
    
    if forced_result:
        print(f"Content length: {len(forced_result.content)}")
        print(f"Content preview: {forced_result.content[:100]}...")
        return True
    
    return False

def test_content_capture():
    """Test the get_current_content method."""
    print("\n🧪 Testing current content capture...")
    
    grouper = StreamingMessageGrouper()
    
    # Test empty state
    empty_content = grouper.get_current_content()
    print(f"Empty grouper content: '{empty_content}'")
    
    # Add content
    mock_response = ClaudeCodeResponse(
        message_type="assistant", 
        content="Test assistant response content",
        is_complete=False,
        session_id="test",
        metadata={}
    )
    
    grouper.add_response(mock_response)
    current_content = grouper.get_current_content()
    print(f"After adding response, content: '{current_content}'")
    
    return len(current_content) > 0

def main():
    """Run validation tests."""
    print("🔧 Validating streaming message persistence fix...\n")
    
    test1_passed = test_grouper_completion()
    test2_passed = test_content_capture()
    
    if test1_passed and test2_passed:
        print("\n✅ Streaming grouper validation passed!")
        print("The fix should now properly capture complete message content.")
        return 0
    else:
        print("\n❌ Streaming grouper validation failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
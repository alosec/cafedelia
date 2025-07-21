#!/usr/bin/env python3
"""
Test script to verify the message persistence fix.

This script tests that streaming Claude Code responses are now properly
captured and persisted to the database with complete content.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the elia_chat module to path
sys.path.insert(0, str(Path(__file__).parent / "elia_chat"))

from database.database import get_session
from database.models import ChatDao, MessageDao
from chats_manager import ChatsManager
from sqlalchemy import select, desc

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

async def test_message_persistence():
    """Test that the most recent chat has proper message persistence."""
    
    log.info("Testing message persistence fix...")
    
    # Get the most recent chat with session_id (our test case)
    async with get_session() as session:
        # Find the problematic session
        problem_session_id = "46bf1d42-0eac-4d0d-a955-e56aefda2a40"
        
        statement = select(ChatDao).where(ChatDao.session_id == problem_session_id)
        result = await session.exec(statement)
        chat = result.first()
        
        if not chat:
            log.error(f"Could not find chat with session_id: {problem_session_id}")
            return False
            
        log.info(f"Found test chat: ID {chat.id}, Title: '{chat.title}'")
        
        # Get messages for this chat
        messages_statement = select(MessageDao).where(MessageDao.chat_id == chat.id).order_by(MessageDao.id)
        messages_result = await session.exec(messages_statement)
        messages = list(messages_result)
        
        log.info(f"Chat has {len(messages)} messages")
        
        # Analyze each message
        for i, msg in enumerate(messages):
            log.info(f"Message {i+1}: Role={msg.role}, Content length={len(msg.content) if msg.content else 0}")
            
            if msg.role == "assistant":
                log.info(f"Assistant message content preview: {msg.content[:200]}..." if msg.content else "EMPTY CONTENT!")
                
                # Check for indicators that this was a proper grouped message
                if msg.content:
                    has_tool_markers = any(marker in msg.content for marker in [
                        "🔧 **Used", "📋 **Tool Result", "**Parameters**"
                    ])
                    has_task_agent = "Task" in msg.content and "prompt" in msg.content
                    content_length = len(msg.content)
                    
                    log.info(f"  - Has tool markers: {has_tool_markers}")
                    log.info(f"  - Has Task agent call: {has_task_agent}")
                    log.info(f"  - Content length: {content_length}")
                    
                    # Check if this looks like the complete response
                    if has_task_agent and "Read cafedelia memory bank" in msg.content:
                        log.info("✅ Found complete Task agent call in database!")
                        return True
                    elif content_length > 500 and has_tool_markers:
                        log.info("✅ Found substantial tool-based content!")
                        return True
                    else:
                        log.warning(f"❌ Assistant content looks incomplete or incorrect")
                else:
                    log.error("❌ Assistant message has no content!")
                    
    log.error("❌ Test failed - no properly persisted assistant content found")
    return False

async def main():
    """Run the message persistence test."""
    try:
        success = await test_message_persistence()
        if success:
            print("\n✅ Message persistence fix appears to be working!")
            return 0
        else:
            print("\n❌ Message persistence fix needs more work")
            return 1
    except Exception as e:
        log.error(f"Test failed with error: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
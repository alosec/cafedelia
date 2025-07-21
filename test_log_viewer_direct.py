#!/usr/bin/env python3
"""
Direct test of the SessionLogViewer to diagnose issues.
"""

import asyncio
import logging
from pathlib import Path
from elia_chat.widgets.session_log_viewer import SessionLogViewer

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

class MockApp:
    def post_message(self, message):
        print(f"Mock app message: {message}")

async def test_log_viewer():
    """Test the log viewer directly"""
    # Known session with log file
    session_id = "005148cc-ff0f-46d2-b10d-aee428ec83f1"
    
    # Create log viewer
    log_viewer = SessionLogViewer()
    log_viewer.app = MockApp()
    
    print(f"Testing with session ID: {session_id}")
    
    # Simulate setting session_id (this should trigger watch_session_id)
    log_viewer.session_id = session_id
    
    # Let it run for a few seconds to see what happens
    await asyncio.sleep(3)
    
    # Check if it's tailing
    print(f"Is tailing: {log_viewer._is_tailing}")
    print(f"Log file path: {log_viewer._log_file_path}")
    
    if log_viewer._log_file_path:
        print(f"File exists: {log_viewer._log_file_path.exists()}")
        if log_viewer._log_file_path.exists():
            print(f"File size: {log_viewer._log_file_path.stat().st_size}")

if __name__ == "__main__":
    asyncio.run(test_log_viewer())
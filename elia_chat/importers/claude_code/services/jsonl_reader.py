"""JSONL file reading and validation for Claude Code sessions"""

import json
from pathlib import Path
from typing import Any, Dict, Iterator


class JsonlReader:
    """Handles reading and parsing JSONL files from Claude Code sessions"""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        
    def read_lines(self) -> list[str]:
        """Read all lines from the JSONL file"""
        with open(self.file_path, "r") as f:
            return f.readlines()
    
    def parse_lines(self, lines: list[str]) -> Iterator[Dict[str, Any]]:
        """Parse JSONL lines into dictionaries, skipping invalid lines"""
        for line_num, line in enumerate(lines, 1):
            try:
                data = json.loads(line.strip())
                yield data
            except json.JSONDecodeError as e:
                # Skip invalid JSON lines silently
                continue
    
    def get_session_metadata(self, lines: list[str], max_lines: int = 10) -> Dict[str, Any]:
        """Extract session metadata from the first few lines of the file"""
        metadata = {
            "session_id": None,
            "summary_title": None,
            "first_timestamp": None,
        }
        
        for line in lines[:max_lines]:
            try:
                data = json.loads(line.strip())
                
                if data.get("type") == "summary" and not metadata["summary_title"]:
                    metadata["summary_title"] = data.get("summary", "Claude Code Session")
                
                if data.get("sessionId") and not metadata["session_id"]:
                    metadata["session_id"] = data.get("sessionId")
                
                if data.get("timestamp") and not metadata["first_timestamp"]:
                    metadata["first_timestamp"] = data.get("timestamp")
                    
            except (json.JSONDecodeError, KeyError):
                continue
        
        return metadata
    
    def count_messages(self, lines: list[str]) -> int:
        """Count the number of valid message entries in the file"""
        count = 0
        for data in self.parse_lines(lines):
            if data.get("type") in ["user", "assistant"]:
                count += 1
        return count
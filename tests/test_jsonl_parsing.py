"""
Tests for JSONL parsing and content extraction in the sync pipeline.

These tests ensure that Claude Code JSONL format is properly parsed and 
tool calls/results are handled correctly to prevent empty messages.
"""

import pytest
from sync.jsonl_transformer import JSONLTransformer


class TestJSONLContentExtraction:
    """Test content extraction from various JSONL message formats."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.transformer = JSONLTransformer()
    
    def test_simple_text_message(self):
        """Test extraction of simple text content."""
        jsonl_data = {
            "type": "user",
            "message": {
                "content": "Hello, how can you help me today?"
            }
        }
        
        content = self.transformer._extract_content(jsonl_data)
        assert content == "Hello, how can you help me today?"
    
    def test_text_content_array(self):
        """Test extraction from content arrays with text blocks."""
        jsonl_data = {
            "type": "assistant", 
            "message": {
                "content": [
                    {"type": "text", "text": "I'll help you with that."},
                    {"type": "text", "text": "Let me search for information."}
                ]
            }
        }
        
        content = self.transformer._extract_content(jsonl_data)
        assert "I'll help you with that." in content
        assert "Let me search for information." in content
    
    def test_tool_use_content(self):
        """Test extraction from messages with tool calls."""
        jsonl_data = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "I'll search for information about Claude Code."},
                    {
                        "type": "tool_use", 
                        "id": "toolu_01Cs7N8vKz8nq", 
                        "name": "WebFetch",
                        "input": {"url": "https://docs.anthropic.com", "prompt": "Find info"}
                    }
                ]
            }
        }
        
        content = self.transformer._extract_content(jsonl_data)
        assert "I'll search for information about Claude Code." in content
        assert "[Used tool: WebFetch" in content
        assert "toolu_01C" in content  # Truncated ID
    
    def test_tool_result_content(self):
        """Test extraction from tool result messages."""
        jsonl_data = {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_01Cs7N8vKz8nq",
                        "content": "Claude Code is a command-line interface for Claude..."
                    }
                ]
            }
        }
        
        content = self.transformer._extract_content(jsonl_data)
        assert "[Tool result: Claude Code is a command-line interface" in content
    
    def test_tool_use_result_field(self):
        """Test extraction from toolUseResult field."""
        jsonl_data = {
            "type": "user",
            "toolUseResult": {
                "result": "Web search completed successfully",
                "url": "https://docs.anthropic.com",
                "durationMs": 5790
            }
        }
        
        content = self.transformer._extract_content(jsonl_data)
        assert "[Tool execution result: Web search completed successfully]" in content
    
    def test_legacy_tool_result_field(self):
        """Test extraction from legacy toolResult field."""
        jsonl_data = {
            "type": "user",
            "toolResult": {
                "output": "Legacy tool execution result"
            }
        }
        
        content = self.transformer._extract_content(jsonl_data)
        assert "[Legacy tool result: Legacy tool execution result" in content
    
    def test_summary_message(self):
        """Test extraction from summary messages."""
        jsonl_data = {
            "type": "summary",
            "summary": "User asked about Claude Code setup and received detailed instructions"
        }
        
        content = self.transformer._extract_content(jsonl_data)
        assert content == "User asked about Claude Code setup and received detailed instructions"
    
    def test_tool_only_assistant_message(self):
        """Test handling of assistant messages with only tool calls (no text)."""
        jsonl_data = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_01Cs7N8vKz8nq", 
                        "name": "WebFetch",
                        "input": {"url": "https://example.com"}
                    }
                ]
            }
        }
        
        content = self.transformer._extract_content(jsonl_data)
        assert "[Used tool: WebFetch" in content
        assert content != ""  # Should not be empty
    
    def test_long_tool_result_truncation(self):
        """Test that very long tool results are truncated."""
        long_result = "x" * 1000  # 1000 character result
        jsonl_data = {
            "type": "user",
            "toolUseResult": {
                "result": long_result
            }
        }
        
        content = self.transformer._extract_content(jsonl_data)
        assert len(content) < 600  # Should be truncated
        assert "..." in content  # Should have truncation indicator


class TestJSONLMessageConversion:
    """Test message conversion and role assignment."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.transformer = JSONLTransformer()
    
    def test_summary_message_role(self):
        """Test that summary messages get system role."""
        jsonl_data = {
            "type": "summary",
            "summary": "Conversation summary"
        }
        
        message_dao = self.transformer._convert_jsonl_message(jsonl_data, chat_id=1)
        assert message_dao.role == "system"
    
    def test_tool_result_message_role(self):
        """Test that tool result messages get user role."""
        jsonl_data = {
            "type": "unknown",
            "toolUseResult": {
                "result": "Tool execution completed"
            }
        }
        
        message_dao = self.transformer._convert_jsonl_message(jsonl_data, chat_id=1)
        assert message_dao.role == "user"
    
    def test_empty_user_message_skipped(self):
        """Test that empty user messages are skipped."""
        jsonl_data = {
            "type": "user",
            "message": {"content": ""}
        }
        
        message_dao = self.transformer._convert_jsonl_message(jsonl_data, chat_id=1)
        assert message_dao is None
    
    def test_tool_only_assistant_message_preserved(self):
        """Test that tool-only assistant messages are preserved with placeholder content."""
        jsonl_data = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_01Cs7N8vKz8nq", 
                        "name": "WebFetch"
                    }
                ]
            }
        }
        
        message_dao = self.transformer._convert_jsonl_message(jsonl_data, chat_id=1)
        assert message_dao is not None
        assert message_dao.role == "assistant"
        assert "[Used tool:" in message_dao.content or "[Assistant used tools]" in message_dao.content
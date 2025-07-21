"""
Specialized widgets for different Claude Code message types.

Provides distinct visual representations for:
- Task agent executions (sidechain Task calls)  
- Tool execution widgets (structured tool calls and results)
- Todo system displays (TodoWrite interactions)
- Standard chat messages (plain text)
"""

import json
from typing import Any, Dict, Optional
from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text
from rich.markdown import Markdown
from rich.syntax import Syntax
from textual.widget import Widget
from textual.reactive import reactive

from elia_chat.models import ChatMessage


class TaskAgentPanel(Widget):
    """Visual representation for sidechain Task agent executions."""
    
    content: reactive[str] = reactive("")
    task_description: reactive[str] = reactive("")
    task_prompt: reactive[str] = reactive("")
    
    def __init__(self, message: ChatMessage, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.content = message.message.get("content", "")
        self._extract_task_info()
    
    def _extract_task_info(self):
        """Extract task description and prompt from message content."""
        try:
            # Parse sidechain metadata for task info
            sidechain_meta = self.message.message.get("meta", {}).get("sidechain_metadata", {})
            tool_input = sidechain_meta.get("tool_input", {})
            
            self.task_description = tool_input.get("description", "Task execution")
            self.task_prompt = tool_input.get("prompt", "")
        except Exception:
            self.task_description = "Task Agent"
            self.task_prompt = ""
    
    def render(self) -> RenderableType:
        """Render the task agent panel with structured information."""
        # Create a panel with task information
        task_content = []
        
        if self.task_description:
            task_content.append(f"**Task**: {self.task_description}")
        
        if self.task_prompt:
            # Truncate very long prompts for display
            prompt_preview = self.task_prompt[:200] + "..." if len(self.task_prompt) > 200 else self.task_prompt
            task_content.append(f"**Prompt**: {prompt_preview}")
        
        # Add the actual content if available
        if self.content and self.content.strip() != "":
            task_content.append("**Output**:")
            task_content.append(self.content)
        
        panel_content = "\n\n".join(task_content)
        
        return Panel(
            Markdown(panel_content),
            title="🔧 Task Agent",
            border_style="blue",
            padding=(0, 1)
        )


class ToolExecutionWidget(Widget):
    """Rich display for tool calls with parameters and results."""
    
    content: reactive[str] = reactive("")
    tool_name: reactive[str] = reactive("")
    tool_params: reactive[Dict[str, Any]] = reactive({})
    
    def __init__(self, message: ChatMessage, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.content = message.message.get("content", "")
        self._extract_tool_info()
    
    def _extract_tool_info(self):
        """Extract tool information from message content."""
        try:
            # Look for tool use patterns in content
            if "🔧 **Used" in self.content:
                # Parse the formatted tool content
                lines = self.content.split('\n')
                for line in lines:
                    if "🔧 **Used" in line:
                        # Extract tool name from formatted content
                        parts = line.split('**Used ')
                        if len(parts) > 1:
                            tool_part = parts[1].split('**')[0].strip()
                            if '(' in tool_part:
                                self.tool_name = tool_part.split('(')[0].strip()
                            else:
                                self.tool_name = tool_part
                        break
            
            # Try to extract parameters from sidechain metadata
            sidechain_meta = self.message.message.get("meta", {}).get("sidechain_metadata", {})
            if "tool_input" in sidechain_meta:
                self.tool_params = sidechain_meta["tool_input"]
                
        except Exception:
            self.tool_name = "Tool"
            self.tool_params = {}
    
    def render(self) -> RenderableType:
        """Render the tool execution with structured display."""
        if not self.tool_name:
            # Fallback to basic content display
            return Markdown(self.content)
        
        # Create a tree structure for tool execution
        tree = Tree(f"🛠️ {self.tool_name}")
        
        # Add parameters if available
        if self.tool_params:
            params_node = tree.add("Parameters")
            for key, value in self.tool_params.items():
                if isinstance(value, dict):
                    param_node = params_node.add(f"{key}:")
                    for subkey, subvalue in value.items():
                        param_node.add(f"{subkey}: {str(subvalue)[:100]}")
                else:
                    params_node.add(f"{key}: {str(value)[:100]}")
        
        # Add result if available
        if self.content:
            result_node = tree.add("Result")
            # Show first few lines of result
            result_lines = self.content.split('\n')[:5]
            for line in result_lines:
                if line.strip():
                    result_node.add(line.strip()[:100])
            
            if len(self.content.split('\n')) > 5:
                result_node.add("...")
        
        return Panel(
            tree,
            title=f"🛠️ {self.tool_name}",
            border_style="green",
            padding=(0, 1)
        )


class TodoSystemDisplay(Widget):
    """Structured display for TodoWrite tool interactions."""
    
    content: reactive[str] = reactive("")
    todos: reactive[list] = reactive([])
    
    def __init__(self, message: ChatMessage, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.content = message.message.get("content", "")
        self._extract_todo_info()
    
    def _extract_todo_info(self):
        """Extract todo information from message content."""
        try:
            # Look for todo data in sidechain metadata
            sidechain_meta = self.message.message.get("meta", {}).get("sidechain_metadata", {})
            tool_input = sidechain_meta.get("tool_input", {})
            
            if "todos" in tool_input:
                self.todos = tool_input["todos"]
            else:
                # Try to parse todos from content
                self._parse_todos_from_content()
                
        except Exception:
            self.todos = []
    
    def _parse_todos_from_content(self):
        """Parse todo items from formatted content."""
        try:
            # Look for JSON-like todo structures in content
            if "[{" in self.content and "}]" in self.content:
                # Extract JSON-like content
                start = self.content.find("[{")
                end = self.content.rfind("}]") + 2
                if start >= 0 and end > start:
                    json_str = self.content[start:end]
                    self.todos = json.loads(json_str)
        except Exception:
            pass
    
    def render(self) -> RenderableType:
        """Render todo system with structured table."""
        if not self.todos:
            # Fallback to regular content display
            return Panel(
                Markdown(self.content),
                title="📋 Todo System",
                border_style="yellow",
                padding=(0, 1)
            )
        
        # Create table for todos
        table = Table(show_header=True, header_style="bold")
        table.add_column("Status", style="bold", width=12)
        table.add_column("Task", ratio=1)
        table.add_column("Priority", width=8)
        
        for todo in self.todos:
            status = todo.get("status", "pending")
            content = todo.get("content", "")
            priority = todo.get("priority", "medium")
            
            # Style status based on completion
            status_style = {
                "completed": "green",
                "in_progress": "blue", 
                "pending": "yellow"
            }.get(status, "white")
            
            # Truncate long task descriptions
            task_display = content[:60] + "..." if len(content) > 60 else content
            
            table.add_row(
                f"[{status_style}]{status}[/{status_style}]",
                task_display,
                priority
            )
        
        return Panel(
            table,
            title=f"📋 Todo System ({len(self.todos)} items)",
            border_style="yellow",
            padding=(0, 1)
        )


class SidechainMessageWidget(Widget):
    """Generic sidechain message widget with metadata display."""
    
    content: reactive[str] = reactive("")
    sidechain_type: reactive[str] = reactive("")
    
    def __init__(self, message: ChatMessage, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.content = message.message.get("content", "")
        self.sidechain_type = message.message.get("meta", {}).get("message_source", "sidechain")
    
    def render(self) -> RenderableType:
        """Render sidechain message with distinctive styling."""
        title = {
            "task": "🔧 Task Execution",
            "tool": "🛠️ Tool Call", 
            "todo": "📋 Todo System",
            "sidechain": "🔗 Sidechain"
        }.get(self.sidechain_type, "🔗 Sidechain")
        
        border_style = {
            "task": "blue",
            "tool": "green",
            "todo": "yellow", 
            "sidechain": "cyan"
        }.get(self.sidechain_type, "cyan")
        
        return Panel(
            Markdown(self.content),
            title=title,
            border_style=border_style,
            padding=(0, 1)
        )


def create_message_widget(message: ChatMessage) -> Widget:
    """Factory function to create appropriate widget based on message type."""
    
    # Check if this is a sidechain message
    is_sidechain = message.message.get("meta", {}).get("is_sidechain", False)
    message_source = message.message.get("meta", {}).get("message_source", "main")
    
    if is_sidechain:
        # Route to specialized sidechain widgets
        if message_source == "task":
            return TaskAgentPanel(message)
        elif message_source == "todo":
            return TodoSystemDisplay(message)  
        elif message_source == "tool":
            return ToolExecutionWidget(message)
        else:
            return SidechainMessageWidget(message)
    
    # For non-sidechain messages, check for tool usage patterns
    content = message.message.get("content", "")
    if "🔧 **Used" in content and "📋 **Tool Result" in content:
        return ToolExecutionWidget(message)
    
    # Default: return None to indicate regular chatbox should be used
    return None
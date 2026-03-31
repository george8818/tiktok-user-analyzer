"""Unit tests for the agent module."""

import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from src.agent.memory import ConversationMemory, Message
from src.agent.tools import ToolRegistry, ToolDefinition, create_default_tools
from src.agent.chat_agent import ChatAgent
from src.agent.prompts import AGENT_SYSTEM_PROMPT


class TestMessage:
    """Tests for Message model."""

    def test_creation(self):
        """Test message creation."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert isinstance(msg.timestamp, datetime)

    def test_to_api_format(self):
        """Test converting to API format."""
        msg = Message(role="assistant", content="Hi there")
        api_msg = msg.to_api_format()
        assert api_msg == {"role": "assistant", "content": "Hi there"}


class TestConversationMemory:
    """Tests for ConversationMemory."""

    def test_add_and_get_messages(self, conversation_memory):
        """Test adding and retrieving messages."""
        conversation_memory.add_message("user", "Hello")
        conversation_memory.add_message("assistant", "Hi there!")

        messages = conversation_memory.get_messages()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_turn_count(self, conversation_memory):
        """Test turn counting."""
        assert conversation_memory.turn_count == 0

        conversation_memory.add_message("user", "Q1")
        conversation_memory.add_message("assistant", "A1")
        assert conversation_memory.turn_count == 1

        conversation_memory.add_message("user", "Q2")
        conversation_memory.add_message("assistant", "A2")
        assert conversation_memory.turn_count == 2

    def test_total_messages(self, conversation_memory):
        """Test total message count."""
        conversation_memory.add_message("user", "msg1")
        conversation_memory.add_message("assistant", "msg2")
        conversation_memory.add_message("user", "msg3")

        assert conversation_memory.total_messages == 3

    def test_max_turns_trimming(self):
        """Test that messages are trimmed when exceeding max turns."""
        memory = ConversationMemory(max_turns=2)

        # Add 5 pairs (exceeds max_turns=2 -> max 4 messages)
        for i in range(5):
            memory.add_message("user", f"Q{i}")
            memory.add_message("assistant", f"A{i}")

        messages = memory.get_messages()
        # Should be trimmed to approximately max_turns * 2
        assert len(messages) <= 5  # Some trimming should occur

    def test_get_last_n_messages(self, conversation_memory):
        """Test getting last N messages."""
        for i in range(5):
            conversation_memory.add_message("user", f"Q{i}")
            conversation_memory.add_message("assistant", f"A{i}")

        last_4 = conversation_memory.get_last_n_messages(4)
        assert len(last_4) == 4
        assert last_4[-1]["content"] == "A4"

    def test_get_full_text(self, conversation_memory):
        """Test full conversation text."""
        conversation_memory.add_message("user", "What is this?")
        conversation_memory.add_message("assistant", "It is a test.")

        text = conversation_memory.get_full_text()
        assert "User: What is this?" in text
        assert "Assistant: It is a test." in text

    def test_summary_handling(self, conversation_memory):
        """Test conversation summary."""
        conversation_memory.set_summary("We discussed user profiling.")

        messages = conversation_memory.get_messages()
        # Summary should be injected as context
        assert len(messages) == 2  # summary + ack
        assert "summary" in messages[0]["content"].lower()

    def test_needs_summary(self):
        """Test summary threshold detection."""
        memory = ConversationMemory(max_turns=20, summary_threshold=3)

        # Below threshold
        for i in range(2):
            memory.add_message("user", f"Q{i}")
            memory.add_message("assistant", f"A{i}")
        assert not memory.needs_summary

        # At threshold
        memory.add_message("user", "Q2")
        memory.add_message("assistant", "A2")
        assert memory.needs_summary

    def test_clear(self, conversation_memory):
        """Test clearing memory."""
        conversation_memory.add_message("user", "test")
        conversation_memory.set_summary("summary")
        conversation_memory.clear()

        assert conversation_memory.turn_count == 0
        assert conversation_memory.total_messages == 0
        messages = conversation_memory.get_messages()
        assert len(messages) == 0

    def test_serialization(self, conversation_memory):
        """Test serialization and deserialization."""
        conversation_memory.add_message("user", "Hello")
        conversation_memory.add_message("assistant", "Hi")
        conversation_memory.set_summary("A greeting")

        data = conversation_memory.to_dict()
        restored = ConversationMemory.from_dict(data)

        assert restored.turn_count == 1
        assert restored._summary == "A greeting"


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_and_get(self):
        """Test registering and retrieving a tool."""
        registry = ToolRegistry()
        registry.register(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "result",
        )

        tool = registry.get_tool("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"

    def test_get_all_tools(self):
        """Test getting all tools in API format."""
        registry = ToolRegistry()
        registry.register(
            name="tool1",
            description="Tool 1",
            parameters={"type": "object"},
            handler=lambda: None,
        )
        registry.register(
            name="tool2",
            description="Tool 2",
            parameters={"type": "object"},
            handler=lambda: None,
        )

        tools = registry.get_all_tools()
        assert len(tools) == 2
        assert tools[0]["name"] == "tool1"

    @pytest.mark.asyncio
    async def test_execute_sync_handler(self):
        """Test executing a sync tool handler."""
        registry = ToolRegistry()
        registry.register(
            name="sync_tool",
            description="Sync",
            parameters={"type": "object"},
            handler=lambda: "sync_result",
        )

        result = await registry.execute("sync_tool")
        assert result.success is True
        assert result.result == "sync_result"

    @pytest.mark.asyncio
    async def test_execute_async_handler(self):
        """Test executing an async tool handler."""
        async def async_handler():
            return "async_result"

        registry = ToolRegistry()
        registry.register(
            name="async_tool",
            description="Async",
            parameters={"type": "object"},
            handler=async_handler,
        )

        result = await registry.execute("async_tool")
        assert result.success is True
        assert result.result == "async_result"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """Test executing an unknown tool."""
        registry = ToolRegistry()
        result = await registry.execute("nonexistent")
        assert result.success is False
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_execute_error_handling(self):
        """Test error handling during tool execution."""
        def failing_handler():
            raise ValueError("Tool failed")

        registry = ToolRegistry()
        registry.register(
            name="failing",
            description="Fails",
            parameters={"type": "object"},
            handler=failing_handler,
        )

        result = await registry.execute("failing")
        assert result.success is False
        assert "Tool failed" in result.error


class TestDefaultTools:
    """Tests for default tool creation."""

    def test_creates_all_default_tools(self):
        """Test that all default tools are created."""
        registry = create_default_tools()
        tools = registry.get_all_tools()

        tool_names = [t["name"] for t in tools]
        assert "get_user_summary" in tool_names
        assert "get_video_analysis" in tool_names
        assert "compare_videos" in tool_names
        assert "get_audience_insights" in tool_names
        assert "get_recommendations" in tool_names
        assert "generate_report" in tool_names


class TestToolDefinition:
    """Tests for ToolDefinition model."""

    def test_to_api_format(self):
        """Test API format conversion."""
        tool = ToolDefinition(
            name="test",
            description="A test tool",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
        )
        api = tool.to_api_format()
        assert api["name"] == "test"
        assert api["description"] == "A test tool"
        assert "input_schema" in api


class TestChatAgent:
    """Tests for ChatAgent."""

    def test_init(self, sample_user_profile):
        """Test agent initialization."""
        agent = ChatAgent(
            api_key="test-key",
            user_profile=sample_user_profile,
        )
        assert agent.user_profile.username == "testuser"
        assert agent.conversation_turn_count == 0

    def test_get_profile_summary(self, sample_user_profile):
        """Test profile summary generation."""
        agent = ChatAgent(
            api_key="test-key",
            user_profile=sample_user_profile,
        )
        summary = agent.get_profile_summary()
        assert "@testuser" in summary
        assert "lifestyle/tech" in summary

    def test_reset_conversation(self, sample_user_profile):
        """Test conversation reset."""
        agent = ChatAgent(
            api_key="test-key",
            user_profile=sample_user_profile,
        )
        agent.memory.add_message("user", "test")
        agent.memory.add_message("assistant", "response")

        agent.reset_conversation()
        assert agent.conversation_turn_count == 0

    def test_system_prompt_contains_profile(self, sample_user_profile):
        """Test that system prompt includes profile context."""
        agent = ChatAgent(
            api_key="test-key",
            user_profile=sample_user_profile,
        )
        assert "@testuser" in agent._system_prompt
        assert "lifestyle/tech" in agent._system_prompt


class TestAgentPrompts:
    """Tests for agent prompt templates."""

    def test_system_prompt_has_placeholder(self):
        """Test system prompt has the context placeholder."""
        assert "{user_profile_context}" in AGENT_SYSTEM_PROMPT

    def test_system_prompt_formatting(self, sample_user_profile):
        """Test system prompt can be formatted with a profile."""
        formatted = AGENT_SYSTEM_PROMPT.format(
            user_profile_context=sample_user_profile.to_context_string()
        )
        assert "@testuser" in formatted
        assert "{user_profile_context}" not in formatted

"""
Conversation memory management for the chat agent.

Implements a sliding window memory with summary capabilities
to maintain context across long conversations.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.logging_config import get_logger

logger = get_logger(__name__)


class Message(BaseModel):
    """A single message in the conversation."""

    role: str = Field(description="Message role: 'user' or 'assistant'")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict, description="Additional metadata")

    def to_api_format(self) -> dict:
        """Convert to Anthropic API message format."""
        return {"role": self.role, "content": self.content}


class ConversationMemory:
    """
    Manages conversation history with sliding window and summarization.

    Keeps the most recent messages in full, and can summarize older
    messages to maintain context without exceeding token limits.

    Usage:
        memory = ConversationMemory(max_turns=20)
        memory.add_message("user", "What content does this user create?")
        memory.add_message("assistant", "Based on the analysis...")
        messages = memory.get_messages()
    """

    def __init__(
        self,
        max_turns: int = 20,
        summary_threshold: int = 15,
    ):
        """
        Initialize conversation memory.

        Args:
            max_turns: Maximum number of message pairs to keep
            summary_threshold: Number of turns before triggering summarization
        """
        self.max_turns = max_turns
        self.summary_threshold = summary_threshold
        self._messages: list[Message] = []
        self._summary: Optional[str] = None
        self._summarized_count: int = 0
        self._total_messages: int = 0

    def add_message(self, role: str, content: str, **metadata) -> None:
        """
        Add a message to the conversation history.

        Args:
            role: 'user' or 'assistant'
            content: Message content
            **metadata: Additional metadata to store
        """
        message = Message(role=role, content=content, metadata=metadata)
        self._messages.append(message)
        self._total_messages += 1

        # Trim if exceeds max
        if len(self._messages) > self.max_turns * 2:
            self._trim_messages()

        logger.debug(
            "message_added",
            role=role,
            total_messages=self._total_messages,
            active_messages=len(self._messages),
        )

    def get_messages(self) -> list[dict]:
        """
        Get messages in Anthropic API format.

        Returns:
            List of message dictionaries for the API
        """
        messages = []

        # Add summary context if available
        if self._summary:
            messages.append({
                "role": "user",
                "content": f"[Previous conversation summary: {self._summary}]",
            })
            messages.append({
                "role": "assistant",
                "content": "I understand. I have the context from our previous discussion.",
            })

        # Add current messages
        for msg in self._messages:
            messages.append(msg.to_api_format())

        return messages

    def get_last_n_messages(self, n: int) -> list[dict]:
        """Get the last N messages in API format."""
        recent = self._messages[-n:] if n < len(self._messages) else self._messages
        return [msg.to_api_format() for msg in recent]

    def get_full_text(self) -> str:
        """Get the full conversation as a text string."""
        parts = []
        if self._summary:
            parts.append(f"[Summary of earlier conversation: {self._summary}]")
        for msg in self._messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            parts.append(f"{role_label}: {msg.content}")
        return "\n\n".join(parts)

    def _trim_messages(self) -> None:
        """Trim messages when exceeding max, keeping recent ones."""
        excess = len(self._messages) - (self.max_turns * 2)
        if excess > 0:
            # Remove oldest messages
            removed = self._messages[:excess]
            self._messages = self._messages[excess:]
            self._summarized_count += len(removed)
            logger.info(
                "messages_trimmed",
                removed=len(removed),
                remaining=len(self._messages),
            )

    def set_summary(self, summary: str) -> None:
        """Set a summary of earlier conversation turns."""
        self._summary = summary
        logger.info("conversation_summary_set", length=len(summary))

    @property
    def turn_count(self) -> int:
        """Number of conversation turns (user-assistant pairs)."""
        return len(self._messages) // 2

    @property
    def total_messages(self) -> int:
        """Total messages since conversation start."""
        return self._total_messages

    @property
    def needs_summary(self) -> bool:
        """Whether the conversation should be summarized."""
        return self.turn_count >= self.summary_threshold and self._summary is None

    def clear(self) -> None:
        """Clear all conversation history."""
        self._messages.clear()
        self._summary = None
        self._summarized_count = 0
        self._total_messages = 0
        logger.info("conversation_memory_cleared")

    def to_dict(self) -> dict:
        """Serialize memory state to dictionary."""
        return {
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata,
                }
                for msg in self._messages
            ],
            "summary": self._summary,
            "summarized_count": self._summarized_count,
            "total_messages": self._total_messages,
        }

    @classmethod
    def from_dict(cls, data: dict, max_turns: int = 20) -> "ConversationMemory":
        """Deserialize memory state from dictionary."""
        memory = cls(max_turns=max_turns)
        for msg_data in data.get("messages", []):
            memory._messages.append(Message(
                role=msg_data["role"],
                content=msg_data["content"],
                timestamp=datetime.fromisoformat(msg_data.get("timestamp", datetime.utcnow().isoformat())),
                metadata=msg_data.get("metadata", {}),
            ))
        memory._summary = data.get("summary")
        memory._summarized_count = data.get("summarized_count", 0)
        memory._total_messages = data.get("total_messages", 0)
        return memory

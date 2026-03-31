"""
Conversational Chat Agent for TikTok User Analysis.

The main agent that handles user Q&A about analyzed TikTok profiles.
Implements tool-augmented reasoning with conversation memory.
"""

import json
from typing import Optional, AsyncIterator

import anthropic

from src.logging_config import get_logger
from src.agent.memory import ConversationMemory
from src.agent.prompts import (
    AGENT_SYSTEM_PROMPT,
    QA_PROMPT,
    FOLLOWUP_PROMPT,
    REPORT_PROMPT,
)
from src.agent.tools import ToolRegistry, create_default_tools
from src.analyzer.models import UserProfile

logger = get_logger(__name__)


class AgentError(Exception):
    """Raised when the agent encounters an error."""


class ChatAgent:
    """
    Conversational agent for answering questions about TikTok users.

    The agent maintains conversation context, uses the analyzed user profile
    as its knowledge base, and can generate various types of insights.

    Usage:
        agent = ChatAgent(
            api_key="sk-ant-...",
            user_profile=profile,
        )
        response = await agent.chat("What kind of content does this user create?")
        suggestions = await agent.get_follow_up_suggestions()
    """

    def __init__(
        self,
        api_key: str,
        user_profile: UserProfile,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.4,
        max_conversation_turns: int = 20,
        tools: Optional[ToolRegistry] = None,
    ):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.user_profile = user_profile
        self.memory = ConversationMemory(max_turns=max_conversation_turns)
        self.tools = tools or create_default_tools()

        # Build the system prompt with user profile context
        self._system_prompt = AGENT_SYSTEM_PROMPT.format(
            user_profile_context=user_profile.to_context_string()
        )

        logger.info(
            "agent_initialized",
            username=user_profile.username,
            model=model,
        )

    async def chat(self, message: str) -> str:
        """
        Send a message and get a response.

        Args:
            message: The user's question or message

        Returns:
            The agent's response text

        Raises:
            AgentError: If the agent fails to generate a response
        """
        logger.info("agent_chat", message_length=len(message))

        # Add user message to memory
        self.memory.add_message("user", message)

        try:
            # Build messages for API call
            messages = self.memory.get_messages()

            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self._system_prompt,
                messages=messages,
                tools=self.tools.get_all_tools(),
            )

            # Process response - handle tool use if needed
            response_text = await self._process_response(response, messages)

            # Add assistant response to memory
            self.memory.add_message("assistant", response_text)

            # Check if we need to summarize the conversation
            if self.memory.needs_summary:
                await self._summarize_conversation()

            return response_text

        except anthropic.APIError as e:
            logger.error("api_error", error=str(e))
            raise AgentError(f"API error: {str(e)}") from e
        except Exception as e:
            logger.error("agent_error", error=str(e))
            raise AgentError(f"Agent error: {str(e)}") from e

    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        """
        Send a message and stream the response.

        Args:
            message: The user's question

        Yields:
            Response text chunks as they are generated
        """
        logger.info("agent_chat_stream", message_length=len(message))

        self.memory.add_message("user", message)
        messages = self.memory.get_messages()

        full_response = ""

        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self._system_prompt,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    full_response += text
                    yield text

            self.memory.add_message("assistant", full_response)

        except Exception as e:
            logger.error("stream_error", error=str(e))
            raise AgentError(f"Streaming error: {str(e)}") from e

    async def _process_response(
        self,
        response: anthropic.types.Message,
        messages: list[dict],
    ) -> str:
        """
        Process the API response, handling tool use if present.

        Implements a tool use loop: if the model wants to use a tool,
        execute it and send the result back for the model to incorporate.
        """
        # Check if there's a tool use request
        tool_use_blocks = [
            block for block in response.content
            if block.type == "tool_use"
        ]

        if not tool_use_blocks:
            # Simple text response
            text_blocks = [
                block.text for block in response.content
                if block.type == "text"
            ]
            return "\n".join(text_blocks)

        # Execute tools and build follow-up messages
        tool_results = []
        for tool_block in tool_use_blocks:
            result = await self.tools.execute(
                tool_block.name,
                **tool_block.input,
            )

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": json.dumps(result.result) if result.success else result.error,
            })

        # Send tool results back to get final response
        updated_messages = messages + [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": tool_results},
        ]

        follow_up = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=self._system_prompt,
            messages=updated_messages,
        )

        text_blocks = [
            block.text for block in follow_up.content
            if block.type == "text"
        ]
        return "\n".join(text_blocks)

    async def get_follow_up_suggestions(self) -> list[str]:
        """
        Generate suggested follow-up questions.

        Returns:
            List of suggested questions
        """
        prompt = FOLLOWUP_PROMPT.format(username=self.user_profile.username)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.7,
                system=self._system_prompt,
                messages=[
                    *self.memory.get_messages(),
                    {"role": "user", "content": prompt},
                ],
            )

            text = response.content[0].text.strip()
            # Clean and parse JSON
            text = text.replace("```json", "").replace("```", "").strip()
            suggestions = json.loads(text)
            return suggestions[:3]

        except (json.JSONDecodeError, Exception) as e:
            logger.warning("followup_generation_failed", error=str(e))
            return [
                f"What content categories does @{self.user_profile.username} focus on?",
                f"Who is @{self.user_profile.username}'s target audience?",
                f"What growth strategies would you recommend?",
            ]

    async def generate_report(self) -> str:
        """
        Generate a comprehensive markdown report about the user.

        Returns:
            Markdown-formatted report string
        """
        prompt = REPORT_PROMPT.format(
            username=self.user_profile.username,
            user_profile_context=self.user_profile.to_context_string(),
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error("report_generation_failed", error=str(e))
            raise AgentError(f"Report generation failed: {str(e)}") from e

    async def _summarize_conversation(self) -> None:
        """Summarize the conversation to maintain context efficiently."""
        try:
            full_text = self.memory.get_full_text()
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.2,
                messages=[{
                    "role": "user",
                    "content": (
                        "Summarize the key points and context from this conversation "
                        "in 3-4 sentences. Focus on what was discussed, what insights "
                        "were shared, and any ongoing questions:\n\n"
                        f"{full_text}"
                    ),
                }],
            )
            summary = response.content[0].text
            self.memory.set_summary(summary)
        except Exception as e:
            logger.warning("summarization_failed", error=str(e))

    def reset_conversation(self) -> None:
        """Reset the conversation history."""
        self.memory.clear()
        logger.info("conversation_reset", username=self.user_profile.username)

    @property
    def conversation_turn_count(self) -> int:
        """Get the current conversation turn count."""
        return self.memory.turn_count

    def get_profile_summary(self) -> str:
        """Get a quick summary of the loaded user profile."""
        p = self.user_profile
        return (
            f"Profile loaded: @{p.username} ({p.display_name})\n"
            f"Creator Type: {p.creator_type}\n"
            f"Niche: {p.niche}\n"
            f"Videos Analyzed: {p.videos_analyzed}\n"
            f"Confidence Score: {p.confidence_score:.0%}"
        )

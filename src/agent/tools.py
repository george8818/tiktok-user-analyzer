"""
Tool definitions for the agent.

Defines the tools available to the agent for answering questions,
generating reports, and performing analysis tasks.
"""

from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from src.logging_config import get_logger

logger = get_logger(__name__)


class ToolDefinition(BaseModel):
    """Definition of an agent tool."""

    name: str = Field(description="Tool name")
    description: str = Field(description="What the tool does")
    parameters: dict = Field(description="JSON schema for parameters")

    def to_api_format(self) -> dict:
        """Convert to Anthropic tool use API format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


class ToolResult(BaseModel):
    """Result from executing a tool."""

    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None


class ToolRegistry:
    """
    Registry of available tools for the agent.

    Manages tool definitions and their handler functions.
    Tools can be registered dynamically and executed by name.
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable,
    ) -> None:
        """Register a new tool."""
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
        )
        self._handlers[name] = handler
        logger.info("tool_registered", name=name)

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool definition by name."""
        return self._tools.get(name)

    def get_all_tools(self) -> list[dict]:
        """Get all tool definitions in API format."""
        return [tool.to_api_format() for tool in self._tools.values()]

    async def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name with given parameters."""
        handler = self._handlers.get(name)
        if not handler:
            return ToolResult(
                tool_name=name,
                success=False,
                error=f"Unknown tool: {name}",
            )

        try:
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**kwargs)
            else:
                result = handler(**kwargs)

            return ToolResult(tool_name=name, success=True, result=result)
        except Exception as e:
            logger.error("tool_execution_error", tool=name, error=str(e))
            return ToolResult(tool_name=name, success=False, error=str(e))


def create_default_tools() -> ToolRegistry:
    """Create the default tool registry with built-in tools."""
    registry = ToolRegistry()

    # Tool: Get user summary
    registry.register(
        name="get_user_summary",
        description="Get a brief summary of the TikTok user's profile and content style",
        parameters={
            "type": "object",
            "properties": {
                "detail_level": {
                    "type": "string",
                    "enum": ["brief", "detailed"],
                    "description": "Level of detail for the summary",
                },
            },
            "required": [],
        },
        handler=lambda **kwargs: "Use the profile context to generate a summary.",
    )

    # Tool: Get video details
    registry.register(
        name="get_video_analysis",
        description="Get detailed analysis for a specific video",
        parameters={
            "type": "object",
            "properties": {
                "video_index": {
                    "type": "integer",
                    "description": "Index of the video (0-based)",
                },
            },
            "required": ["video_index"],
        },
        handler=lambda **kwargs: f"Retrieve analysis for video index {kwargs.get('video_index', 0)}.",
    )

    # Tool: Compare videos
    registry.register(
        name="compare_videos",
        description="Compare two videos from the user's profile",
        parameters={
            "type": "object",
            "properties": {
                "aspect": {
                    "type": "string",
                    "description": "Aspect to compare (engagement, content, style, audience)",
                },
            },
            "required": [],
        },
        handler=lambda **kwargs: "Compare the analyzed videos.",
    )

    # Tool: Get audience insights
    registry.register(
        name="get_audience_insights",
        description="Get insights about the user's likely audience demographics and behavior",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=lambda **kwargs: "Provide audience analysis based on profile data.",
    )

    # Tool: Get recommendations
    registry.register(
        name="get_recommendations",
        description="Get content or growth recommendations for the user",
        parameters={
            "type": "object",
            "properties": {
                "focus_area": {
                    "type": "string",
                    "enum": ["content", "growth", "engagement", "monetization"],
                    "description": "Area to focus recommendations on",
                },
            },
            "required": [],
        },
        handler=lambda **kwargs: "Generate recommendations based on the analysis.",
    )

    # Tool: Generate report
    registry.register(
        name="generate_report",
        description="Generate a formatted report about the user",
        parameters={
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["markdown", "brief", "detailed"],
                    "description": "Report format",
                },
            },
            "required": [],
        },
        handler=lambda **kwargs: "Generate a comprehensive report.",
    )

    return registry

"""
FastAPI REST API for TikTok User Analyzer.

Provides HTTP endpoints for:
- Triggering user analysis
- Querying user profiles
- Chat-based Q&A about users
- Generating reports
"""

import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.config import get_settings
from src.logging_config import setup_logging, get_logger
from src.pipeline import AnalysisPipeline
from src.agent.chat_agent import ChatAgent
from src.analyzer.models import UserProfile

logger = get_logger(__name__)


# --- Request/Response Models ---

class AnalyzeRequest(BaseModel):
    """Request to analyze a TikTok user."""
    username: str = Field(description="TikTok username (with or without @)")
    max_videos: int = Field(default=2, ge=1, le=5, description="Max videos to analyze")
    use_mock: bool = Field(default=False, description="Use mock data for testing")


class AnalyzeResponse(BaseModel):
    """Response from user analysis."""
    username: str
    creator_type: str
    niche: str
    profile_summary: str
    videos_analyzed: int
    confidence_score: float
    primary_topics: list[str]


class ChatRequest(BaseModel):
    """Request for the chat endpoint."""
    message: str = Field(description="User's question about the analyzed profile")
    session_id: Optional[str] = Field(default=None, description="Conversation session ID")


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    response: str
    session_id: str
    turn_count: int
    follow_up_suggestions: list[str] = Field(default_factory=list)


class ProfileListItem(BaseModel):
    """Summary of a cached profile."""
    username: str
    creator_type: str
    niche: str
    videos_analyzed: int
    updated_at: Optional[str] = None


class ReportRequest(BaseModel):
    """Request to generate a report."""
    username: str


class ReportResponse(BaseModel):
    """Generated report."""
    username: str
    report_markdown: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


# --- Application Setup ---

# In-memory agent store (keyed by session_id)
_agents: dict[str, ChatAgent] = {}
_pipeline: Optional[AnalysisPipeline] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _pipeline
    settings = get_settings()
    setup_logging(level=settings.logging.level, log_format=settings.logging.format)

    _pipeline = AnalysisPipeline(settings)
    await _pipeline.initialize()
    logger.info("api_started", host=settings.api.host, port=settings.api.port)

    yield

    await _pipeline.close()
    logger.info("api_stopped")


app = FastAPI(
    title="TikTok User Analyzer",
    description="AI-powered TikTok user profiling and analysis agent",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Endpoints ---

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze_user(request: AnalyzeRequest):
    """
    Analyze a TikTok user.

    Scrapes the user's profile and recent videos, analyzes them
    using multimodal LLM, and generates a comprehensive profile.
    """
    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    try:
        profile = await _pipeline.analyze_user(
            username=request.username,
            max_videos=request.max_videos,
            use_mock=request.use_mock,
        )

        return AnalyzeResponse(
            username=profile.username,
            creator_type=profile.creator_type,
            niche=profile.niche,
            profile_summary=profile.profile_summary,
            videos_analyzed=profile.videos_analyzed,
            confidence_score=profile.confidence_score,
            primary_topics=profile.primary_topics,
        )

    except Exception as e:
        logger.error("analyze_error", error=str(e), username=request.username)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/profiles", response_model=list[ProfileListItem])
async def list_profiles():
    """List all analyzed profiles."""
    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    profiles = await _pipeline.get_cached_profiles()
    return [ProfileListItem(**p) for p in profiles]


@app.get("/api/v1/profiles/{username}")
async def get_profile(username: str):
    """Get a specific user's profile."""
    if not _pipeline or not _pipeline._repo:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    profile = await _pipeline._repo.get_profile(username)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile not found: @{username}")

    return profile.model_dump(mode="json")


@app.post("/api/v1/chat/{username}", response_model=ChatResponse)
async def chat(username: str, request: ChatRequest):
    """
    Chat with the AI agent about a specific user.

    First-time calls create a new conversation session.
    Pass session_id for follow-up messages.
    """
    if not _pipeline or not _pipeline._repo:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    # Get or create agent
    session_id = request.session_id or str(uuid.uuid4())

    if session_id not in _agents:
        # Load profile
        profile = await _pipeline._repo.get_profile(username)
        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"Profile not found: @{username}. Run /analyze first.",
            )
        _agents[session_id] = _pipeline.create_agent(profile)

    agent = _agents[session_id]

    try:
        response = await agent.chat(request.message)
        suggestions = await agent.get_follow_up_suggestions()

        return ChatResponse(
            response=response,
            session_id=session_id,
            turn_count=agent.conversation_turn_count,
            follow_up_suggestions=suggestions,
        )

    except Exception as e:
        logger.error("chat_error", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/report/{username}", response_model=ReportResponse)
async def generate_report(username: str):
    """Generate a comprehensive report for a user."""
    if not _pipeline or not _pipeline._repo:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    profile = await _pipeline._repo.get_profile(username)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile not found: @{username}")

    agent = _pipeline.create_agent(profile)

    try:
        report = await agent.generate_report()
        return ReportResponse(username=username, report_markdown=report)
    except Exception as e:
        logger.error("report_error", error=str(e), username=username)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/profiles/{username}")
async def delete_profile(username: str):
    """Delete a user's profile and all related data."""
    if not _pipeline or not _pipeline._repo:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    deleted = await _pipeline._repo.delete_profile(username)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Profile not found: @{username}")

    return {"message": f"Profile @{username} deleted successfully"}


@app.delete("/api/v1/chat/{session_id}")
async def end_chat(session_id: str):
    """End a chat session."""
    if session_id in _agents:
        del _agents[session_id]
        return {"message": "Chat session ended"}
    raise HTTPException(status_code=404, detail="Session not found")

"""
Repository layer for database operations.
Provides async CRUD operations for user profiles, analyses, and conversations.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.logging_config import get_logger
from src.storage.db_models import Base, UserProfileDB, VideoAnalysisDB, ConversationDB
from src.analyzer.models import UserProfile, VideoAnalysisResult

logger = get_logger(__name__)


class Repository:
    """
    Async repository for database operations.

    Provides CRUD operations for all stored entities using SQLAlchemy
    async sessions.

    Usage:
        repo = Repository(database_url="sqlite+aiosqlite:///./data/app.db")
        await repo.initialize()
        await repo.save_profile(user_profile)
        profile = await repo.get_profile("username")
    """

    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def initialize(self) -> None:
        """Create database tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_initialized")

    async def close(self) -> None:
        """Close the database engine."""
        await self.engine.dispose()

    # --- User Profile Operations ---

    async def save_profile(self, profile: UserProfile) -> UserProfileDB:
        """Save or update a user profile."""
        async with self.session_factory() as session:
            # Check if profile exists
            existing = await self._get_profile_db(session, profile.username)

            if existing:
                # Update existing
                existing.display_name = profile.display_name
                existing.bio = profile.bio
                existing.profile_summary = profile.profile_summary
                existing.creator_type = profile.creator_type
                existing.niche = profile.niche
                existing.influence_tier = profile.estimated_influence_tier
                existing.primary_topics = profile.primary_topics
                existing.content_format = profile.content_format
                existing.posting_style = profile.posting_style
                existing.strengths = profile.strengths
                existing.areas_for_improvement = profile.areas_for_improvement
                existing.confidence_score = profile.confidence_score
                existing.videos_analyzed = profile.videos_analyzed
                existing.full_profile_json = profile.model_dump(mode="json")
                existing.updated_at = datetime.utcnow()
                db_profile = existing
            else:
                # Create new
                db_profile = UserProfileDB(
                    username=profile.username,
                    display_name=profile.display_name,
                    bio=profile.bio,
                    profile_summary=profile.profile_summary,
                    creator_type=profile.creator_type,
                    niche=profile.niche,
                    influence_tier=profile.estimated_influence_tier,
                    primary_topics=profile.primary_topics,
                    content_format=profile.content_format,
                    posting_style=profile.posting_style,
                    strengths=profile.strengths,
                    areas_for_improvement=profile.areas_for_improvement,
                    confidence_score=profile.confidence_score,
                    videos_analyzed=profile.videos_analyzed,
                    full_profile_json=profile.model_dump(mode="json"),
                )
                session.add(db_profile)

            await session.commit()
            await session.refresh(db_profile)

            logger.info("profile_saved", username=profile.username, id=db_profile.id)
            return db_profile

    async def get_profile(self, username: str) -> Optional[UserProfile]:
        """Get a user profile by username."""
        async with self.session_factory() as session:
            db_profile = await self._get_profile_db(session, username)
            if not db_profile or not db_profile.full_profile_json:
                return None

            return UserProfile(**db_profile.full_profile_json)

    async def list_profiles(self) -> list[dict]:
        """List all stored profiles (summary only)."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(UserProfileDB).order_by(UserProfileDB.updated_at.desc())
            )
            profiles = result.scalars().all()

            return [
                {
                    "username": p.username,
                    "display_name": p.display_name,
                    "creator_type": p.creator_type,
                    "niche": p.niche,
                    "videos_analyzed": p.videos_analyzed,
                    "confidence_score": p.confidence_score,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in profiles
            ]

    async def delete_profile(self, username: str) -> bool:
        """Delete a user profile and all related data."""
        async with self.session_factory() as session:
            db_profile = await self._get_profile_db(session, username)
            if not db_profile:
                return False

            await session.delete(db_profile)
            await session.commit()
            logger.info("profile_deleted", username=username)
            return True

    async def _get_profile_db(
        self, session: AsyncSession, username: str
    ) -> Optional[UserProfileDB]:
        """Get a profile DB object by username."""
        result = await session.execute(
            select(UserProfileDB).where(UserProfileDB.username == username)
        )
        return result.scalar_one_or_none()

    # --- Video Analysis Operations ---

    async def save_video_analysis(
        self,
        username: str,
        analysis: VideoAnalysisResult,
    ) -> Optional[VideoAnalysisDB]:
        """Save a video analysis result."""
        async with self.session_factory() as session:
            db_profile = await self._get_profile_db(session, username)
            if not db_profile:
                logger.warning("profile_not_found_for_video", username=username)
                return None

            db_analysis = VideoAnalysisDB(
                video_id=analysis.video_id,
                user_profile_id=db_profile.id,
                video_url=analysis.video_url,
                content_summary=analysis.content_summary,
                content_category=analysis.content_category,
                content_themes=analysis.content_themes,
                tone=analysis.tone,
                target_audience=analysis.target_audience,
                production_quality=analysis.production_quality,
                views=analysis.views,
                likes=analysis.likes,
                comments=analysis.comments,
                description=analysis.description,
                hashtags=analysis.hashtags,
                full_analysis_json=analysis.model_dump(mode="json"),
            )
            session.add(db_analysis)
            await session.commit()
            await session.refresh(db_analysis)

            logger.info("video_analysis_saved", video_id=analysis.video_id)
            return db_analysis

    # --- Conversation Operations ---

    async def create_conversation(self, username: str) -> str:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())

        async with self.session_factory() as session:
            db_profile = await self._get_profile_db(session, username)
            if not db_profile:
                raise ValueError(f"Profile not found: {username}")

            conv = ConversationDB(
                session_id=session_id,
                user_profile_id=db_profile.id,
                messages_json=[],
            )
            session.add(conv)
            await session.commit()

            logger.info("conversation_created", session_id=session_id, username=username)
            return session_id

    async def save_conversation(
        self,
        session_id: str,
        messages: list[dict],
        summary: Optional[str] = None,
    ) -> None:
        """Save conversation messages."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(ConversationDB).where(ConversationDB.session_id == session_id)
            )
            conv = result.scalar_one_or_none()
            if not conv:
                logger.warning("conversation_not_found", session_id=session_id)
                return

            conv.messages_json = messages
            conv.summary = summary
            conv.turn_count = len(messages) // 2
            conv.updated_at = datetime.utcnow()
            await session.commit()

    async def get_conversation(self, session_id: str) -> Optional[dict]:
        """Get a conversation by session ID."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(ConversationDB).where(ConversationDB.session_id == session_id)
            )
            conv = result.scalar_one_or_none()
            if not conv:
                return None

            return {
                "session_id": conv.session_id,
                "messages": conv.messages_json,
                "summary": conv.summary,
                "turn_count": conv.turn_count,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            }

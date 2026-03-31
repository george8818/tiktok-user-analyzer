"""
SQLAlchemy database models for persistent storage.
Stores user profiles, video analyses, and conversation sessions.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


class UserProfileDB(Base):
    """Stored user profile."""

    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200), default="")
    bio = Column(Text, default="")
    profile_url = Column(String(500), default="")
    is_verified = Column(Boolean, default=False)
    region = Column(String(50), nullable=True)

    # Stats
    followers = Column(Integer, default=0)
    following = Column(Integer, default=0)
    total_likes = Column(Integer, default=0)
    video_count = Column(Integer, default=0)

    # Generated profile
    profile_summary = Column(Text, default="")
    creator_type = Column(String(100), default="")
    niche = Column(String(200), default="")
    influence_tier = Column(String(50), default="")
    primary_topics = Column(JSON, default=list)
    content_format = Column(String(200), default="")
    posting_style = Column(Text, default="")
    strengths = Column(JSON, default=list)
    areas_for_improvement = Column(JSON, default=list)

    # Full profile JSON for complete data
    full_profile_json = Column(JSON, nullable=True)

    # Metadata
    confidence_score = Column(Float, default=0.0)
    videos_analyzed = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    video_analyses = relationship(
        "VideoAnalysisDB",
        back_populates="user_profile",
        cascade="all, delete-orphan",
    )
    conversations = relationship(
        "ConversationDB",
        back_populates="user_profile",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<UserProfileDB(username='{self.username}', creator_type='{self.creator_type}')>"


class VideoAnalysisDB(Base):
    """Stored video analysis result."""

    __tablename__ = "video_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(100), nullable=False, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    video_url = Column(String(500), default="")

    # Analysis results
    content_summary = Column(Text, default="")
    content_category = Column(String(100), default="")
    content_themes = Column(JSON, default=list)
    tone = Column(String(100), default="")
    target_audience = Column(String(200), default="")
    production_quality = Column(String(50), default="")

    # Engagement
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)

    # Metadata
    description = Column(Text, default="")
    hashtags = Column(JSON, default=list)
    full_analysis_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user_profile = relationship("UserProfileDB", back_populates="video_analyses")

    def __repr__(self) -> str:
        return f"<VideoAnalysisDB(video_id='{self.video_id}', category='{self.content_category}')>"


class ConversationDB(Base):
    """Stored conversation session."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)

    # Conversation data
    messages_json = Column(JSON, default=list)
    summary = Column(Text, nullable=True)
    turn_count = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user_profile = relationship("UserProfileDB", back_populates="conversations")

    def __repr__(self) -> str:
        return f"<ConversationDB(session_id='{self.session_id}', turns={self.turn_count})>"

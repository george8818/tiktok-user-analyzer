"""Unit tests for the storage module."""

import pytest
import pytest_asyncio
from pathlib import Path

from src.storage.repository import Repository
from src.storage.db_models import Base, UserProfileDB, VideoAnalysisDB, ConversationDB


class TestRepository:
    """Tests for the Repository class."""

    @pytest_asyncio.fixture
    async def repo(self, tmp_path):
        """Create a test repository with in-memory SQLite."""
        db_path = tmp_path / "test.db"
        repo = Repository(f"sqlite+aiosqlite:///{db_path}")
        await repo.initialize()
        yield repo
        await repo.close()

    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, repo):
        """Test that initialization creates database tables."""
        # If we get here without error, tables were created
        profiles = await repo.list_profiles()
        assert isinstance(profiles, list)
        assert len(profiles) == 0

    @pytest.mark.asyncio
    async def test_save_and_get_profile(self, repo, sample_user_profile):
        """Test saving and retrieving a profile."""
        await repo.save_profile(sample_user_profile)

        loaded = await repo.get_profile("testuser")
        assert loaded is not None
        assert loaded.username == "testuser"
        assert loaded.creator_type == "lifestyle/tech"
        assert loaded.videos_analyzed == 2

    @pytest.mark.asyncio
    async def test_save_profile_update(self, repo, sample_user_profile):
        """Test updating an existing profile."""
        await repo.save_profile(sample_user_profile)

        # Modify and save again
        sample_user_profile.creator_type = "tech_only"
        sample_user_profile.confidence_score = 0.95
        await repo.save_profile(sample_user_profile)

        loaded = await repo.get_profile("testuser")
        assert loaded.creator_type == "tech_only"
        assert loaded.confidence_score == 0.95

    @pytest.mark.asyncio
    async def test_get_nonexistent_profile(self, repo):
        """Test getting a profile that doesn't exist."""
        result = await repo.get_profile("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_profiles(self, repo, sample_user_profile):
        """Test listing all profiles."""
        await repo.save_profile(sample_user_profile)

        profiles = await repo.list_profiles()
        assert len(profiles) == 1
        assert profiles[0]["username"] == "testuser"
        assert profiles[0]["creator_type"] == "lifestyle/tech"

    @pytest.mark.asyncio
    async def test_delete_profile(self, repo, sample_user_profile):
        """Test deleting a profile."""
        await repo.save_profile(sample_user_profile)

        deleted = await repo.delete_profile("testuser")
        assert deleted is True

        result = await repo.get_profile("testuser")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_profile(self, repo):
        """Test deleting a profile that doesn't exist."""
        deleted = await repo.delete_profile("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_save_video_analysis(
        self, repo, sample_user_profile, sample_video_analysis
    ):
        """Test saving a video analysis."""
        await repo.save_profile(sample_user_profile)

        result = await repo.save_video_analysis("testuser", sample_video_analysis)
        assert result is not None
        assert result.video_id == sample_video_analysis.video_id

    @pytest.mark.asyncio
    async def test_save_video_analysis_no_profile(self, repo, sample_video_analysis):
        """Test saving analysis without a profile."""
        result = await repo.save_video_analysis("nonexistent", sample_video_analysis)
        assert result is None

    @pytest.mark.asyncio
    async def test_create_conversation(self, repo, sample_user_profile):
        """Test creating a conversation session."""
        await repo.save_profile(sample_user_profile)

        session_id = await repo.create_conversation("testuser")
        assert session_id is not None
        assert len(session_id) > 0

    @pytest.mark.asyncio
    async def test_create_conversation_no_profile(self, repo):
        """Test creating conversation without profile raises error."""
        with pytest.raises(ValueError, match="Profile not found"):
            await repo.create_conversation("nonexistent")

    @pytest.mark.asyncio
    async def test_save_and_get_conversation(self, repo, sample_user_profile):
        """Test saving and retrieving conversation messages."""
        await repo.save_profile(sample_user_profile)
        session_id = await repo.create_conversation("testuser")

        messages = [
            {"role": "user", "content": "What content does this user create?"},
            {"role": "assistant", "content": "This user creates tech and lifestyle content."},
        ]
        await repo.save_conversation(session_id, messages, summary="Discussed content type")

        conv = await repo.get_conversation(session_id)
        assert conv is not None
        assert conv["session_id"] == session_id
        assert len(conv["messages"]) == 2
        assert conv["summary"] == "Discussed content type"
        assert conv["turn_count"] == 1

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(self, repo):
        """Test getting a conversation that doesn't exist."""
        result = await repo.get_conversation("nonexistent-session")
        assert result is None


class TestDBModels:
    """Tests for SQLAlchemy model representations."""

    def test_user_profile_repr(self):
        """Test UserProfileDB string representation."""
        profile = UserProfileDB(username="testuser", creator_type="tech")
        assert "testuser" in repr(profile)
        assert "tech" in repr(profile)

    def test_video_analysis_repr(self):
        """Test VideoAnalysisDB string representation."""
        analysis = VideoAnalysisDB(video_id="vid123", content_category="lifestyle")
        assert "vid123" in repr(analysis)
        assert "lifestyle" in repr(analysis)

    def test_conversation_repr(self):
        """Test ConversationDB string representation."""
        conv = ConversationDB(session_id="sess-123", turn_count=5)
        assert "sess-123" in repr(conv)

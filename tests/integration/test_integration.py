"""
Integration tests for the TikTok User Analyzer.

Tests the interaction between multiple modules (scraper, analyzer,
storage, agent) without external API dependencies.
"""

import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import json

from src.scraper.tiktok_scraper import MockTikTokScraper
from src.scraper.models import ScrapedData
from src.analyzer.models import UserProfile, VideoAnalysisResult
from src.agent.chat_agent import ChatAgent
from src.agent.memory import ConversationMemory
from src.storage.repository import Repository


class TestScraperToAnalyzerIntegration:
    """Tests for scraper output feeding into analyzer."""

    @pytest.mark.asyncio
    async def test_mock_scraper_produces_analyzable_data(self):
        """Test that mock scraper output is suitable for analysis."""
        scraper = MockTikTokScraper()
        async with scraper:
            data = await scraper.scrape_user("integrationtest", max_videos=2)

        # Verify the data structure is complete enough for analysis
        assert data.user.username == "integrationtest"
        assert len(data.user.videos) == 2

        # Check each video has the fields needed by the analyzer
        for video in data.user.videos:
            assert video.video_id
            assert video.url
            assert video.description
            assert len(video.hashtags) > 0
            assert video.stats.views > 0

            # Test that analysis text can be generated
            text = video.to_analysis_text()
            assert len(text) > 50  # Should be substantial

        # Test user analysis text
        user_text = data.user.to_analysis_text()
        assert "@integrationtest" in user_text
        assert "Video 1" in user_text
        assert "Video 2" in user_text

    @pytest.mark.asyncio
    async def test_scraped_data_to_profile_context(
        self, sample_user_profile
    ):
        """Test that a profile generates valid context for the agent."""
        context = sample_user_profile.to_context_string()

        # Context should be comprehensive
        assert len(context) > 500
        assert "Profile Summary" in context
        assert "Creator Classification" in context
        assert "Video Analysis Details" in context

        # Context should be usable in a prompt (no unformatted placeholders)
        assert "{" not in context or "**" in context  # Allow markdown bold


class TestStorageIntegration:
    """Tests for storage persistence across modules."""

    @pytest_asyncio.fixture
    async def repo(self, tmp_path):
        """Create a test repository."""
        db_path = tmp_path / "integration_test.db"
        repo = Repository(f"sqlite+aiosqlite:///{db_path}")
        await repo.initialize()
        yield repo
        await repo.close()

    @pytest.mark.asyncio
    async def test_full_profile_persistence_cycle(
        self, repo, sample_user_profile, sample_video_analysis
    ):
        """Test saving a profile and related data, then retrieving it."""
        # Save profile
        await repo.save_profile(sample_user_profile)

        # Save video analyses
        for va in sample_user_profile.video_analyses:
            await repo.save_video_analysis("testuser", va)

        # Create and save conversation
        session_id = await repo.create_conversation("testuser")
        messages = [
            {"role": "user", "content": "What content does this user create?"},
            {"role": "assistant", "content": "Tech and lifestyle content."},
        ]
        await repo.save_conversation(session_id, messages)

        # Verify everything persisted
        loaded_profile = await repo.get_profile("testuser")
        assert loaded_profile is not None
        assert loaded_profile.username == "testuser"
        assert loaded_profile.videos_analyzed == 2

        profiles_list = await repo.list_profiles()
        assert len(profiles_list) == 1

        conv = await repo.get_conversation(session_id)
        assert conv is not None
        assert len(conv["messages"]) == 2

    @pytest.mark.asyncio
    async def test_profile_update_preserves_data(
        self, repo, sample_user_profile
    ):
        """Test that updating a profile preserves existing data."""
        await repo.save_profile(sample_user_profile)

        # Load and modify
        loaded = await repo.get_profile("testuser")
        loaded.creator_type = "updated_type"
        loaded.confidence_score = 0.99
        await repo.save_profile(loaded)

        # Reload and verify
        reloaded = await repo.get_profile("testuser")
        assert reloaded.creator_type == "updated_type"
        assert reloaded.confidence_score == 0.99
        # Original data should still be present
        assert reloaded.username == "testuser"
        assert len(reloaded.primary_topics) > 0


class TestAgentWithMemoryIntegration:
    """Tests for agent with conversation memory."""

    def test_agent_memory_accumulation(self, sample_user_profile):
        """Test that agent properly accumulates conversation context."""
        agent = ChatAgent(
            api_key="test-key",
            user_profile=sample_user_profile,
            max_conversation_turns=10,
        )

        # Simulate conversation without API calls
        agent.memory.add_message("user", "What topics does this user cover?")
        agent.memory.add_message("assistant", "Tech and lifestyle content.")
        agent.memory.add_message("user", "Tell me about their audience.")
        agent.memory.add_message("assistant", "Young tech professionals.")

        assert agent.conversation_turn_count == 2

        messages = agent.memory.get_messages()
        assert len(messages) == 4
        assert messages[0]["content"] == "What topics does this user cover?"

    def test_agent_reset_clears_memory(self, sample_user_profile):
        """Test that reset clears conversation state."""
        agent = ChatAgent(
            api_key="test-key",
            user_profile=sample_user_profile,
        )

        agent.memory.add_message("user", "test")
        agent.memory.add_message("assistant", "response")
        agent.reset_conversation()

        assert agent.conversation_turn_count == 0
        assert len(agent.memory.get_messages()) == 0

    def test_agent_profile_in_system_prompt(self, sample_user_profile):
        """Test profile data is embedded in system prompt."""
        agent = ChatAgent(
            api_key="test-key",
            user_profile=sample_user_profile,
        )

        # System prompt should contain profile data
        assert sample_user_profile.username in agent._system_prompt
        assert sample_user_profile.creator_type in agent._system_prompt
        assert sample_user_profile.niche in agent._system_prompt


class TestEndToEndMockFlow:
    """Tests for the complete flow using mock data."""

    @pytest.mark.asyncio
    async def test_mock_scrape_to_agent_setup(self, tmp_path):
        """Test the flow from mock scraping to agent initialization."""
        # Step 1: Scrape with mock
        scraper = MockTikTokScraper()
        async with scraper:
            scraped = await scraper.scrape_user("e2e_test", max_videos=2)

        assert scraped.is_complete

        # Step 2: Store in database
        db_path = tmp_path / "e2e_test.db"
        repo = Repository(f"sqlite+aiosqlite:///{db_path}")
        await repo.initialize()

        # Step 3: Create a profile (using fixtures to simulate LLM output)
        profile = UserProfile(
            username=scraped.user.username,
            display_name=scraped.user.display_name,
            bio=scraped.user.bio,
            profile_summary="E2E test creator producing diverse content.",
            creator_type="lifestyle",
            niche="general lifestyle",
            primary_topics=["lifestyle", "tech"],
            content_format="short vlogs",
            posting_style="casual and frequent",
            videos_analyzed=len(scraped.user.videos),
            confidence_score=0.7,
        )

        await repo.save_profile(profile)

        # Step 4: Create agent
        loaded_profile = await repo.get_profile("e2e_test")
        assert loaded_profile is not None

        agent = ChatAgent(
            api_key="test-key",
            user_profile=loaded_profile,
        )

        assert agent.user_profile.username == "e2e_test"
        summary = agent.get_profile_summary()
        assert "e2e_test" in summary

        await repo.close()

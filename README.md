# TikTok User Insight Agent

An AI-powered agent that scrapes TikTok user profiles, analyzes their video content using multimodal LLMs, generates comprehensive user profiles, and enables interactive Q&A about the analyzed creators.

## Architecture Overview

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Scraper    │────>│   Analyzer   │────>│   Profile    │────>│    Agent     │
│  (Playwright │     │  (Claude     │     │  Generator   │     │  (Chat Q&A)  │
│   + yt-dlp)  │     │   Vision)    │     │  (Claude)    │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │                     │
       └────────────────────┴────────────────────┴─────────────────────┘
                                    │
                          ┌──────────────────┐
                          │   SQLite Storage  │
                          │   (Persistence)   │
                          └──────────────────┘
```

### Module Breakdown

| Module | Purpose | Key Tech |
|--------|---------|----------|
| **Scraper** | Profile scraping, video download, frame extraction | Playwright, yt-dlp, OpenCV |
| **Analyzer** | Video content analysis, multimodal understanding | Claude Vision API |
| **Profile Generator** | Synthesize analyses into user profiles | Claude API |
| **Agent** | Conversational Q&A with tool use and memory | Claude API, tool use |
| **Storage** | Persistent storage for profiles and conversations | SQLAlchemy, aiosqlite |
| **API** | REST API for all operations | FastAPI |
| **CLI** | Command-line interface with rich output | Click, Rich |

## Quick Start

### Prerequisites

- Python 3.11+
- An Anthropic API key ([get one here](https://console.anthropic.com/))
- (Optional) Docker & Docker Compose

### Local Setup

```bash
# Clone the repository
git clone <repo-url>
cd tiktok-user-analyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run tests
pytest tests/ -v

# Analyze a user (mock mode for testing)
python -m cli.main analyze charlidamelio --mock --chat
```

### Docker Setup

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# Build and run
docker compose up -d

# Run tests
docker compose run --rm test

# Access the API
curl http://localhost:8000/health
```

## Usage

### CLI Commands

```bash
# Analyze a TikTok user (with live scraping)
python -m cli.main analyze @username --max-videos 2

# Analyze with mock data (no scraping needed)
python -m cli.main analyze @username --mock

# Analyze and start interactive chat
python -m cli.main analyze @username --mock --chat

# Chat with a previously analyzed user
python -m cli.main chat testuser

# List all analyzed profiles
python -m cli.main list

# Generate a report
python -m cli.main report testuser -o report.md

# Start the API server
python -m cli.main serve --port 8000
```

### REST API

```bash
# Health check
GET /health

# Analyze a user
POST /api/v1/analyze
{
  "username": "charlidamelio",
  "max_videos": 2,
  "use_mock": false
}

# List profiles
GET /api/v1/profiles

# Get specific profile
GET /api/v1/profiles/{username}

# Chat about a user
POST /api/v1/chat/{username}
{
  "message": "What content does this user create?",
  "session_id": null
}

# Generate report
POST /api/v1/report/{username}

# Delete profile
DELETE /api/v1/profiles/{username}
```

### Interactive Chat Examples

Once a profile is loaded, you can ask questions like:

- "What kind of content does this user create?"
- "Who is their target audience?"
- "What are their content strengths?"
- "Compare their two most recent videos"
- "What brand partnerships would suit them?"
- "What engagement strategies do they use?"
- "Generate a full report"

## Project Structure

```
tiktok-user-analyzer/
├── src/
│   ├── scraper/           # TikTok data scraping
│   │   ├── models.py      # Data models (User, Video, Stats)
│   │   ├── tiktok_scraper.py  # Playwright-based scraper
│   │   ├── video_downloader.py # yt-dlp video download
│   │   └── frame_extractor.py  # OpenCV frame extraction
│   ├── analyzer/          # Content analysis
│   │   ├── models.py      # Analysis result models
│   │   ├── video_analyzer.py   # Multimodal video analysis
│   │   └── profile_generator.py # Profile synthesis
│   ├── agent/             # Conversational agent
│   │   ├── chat_agent.py  # Main chat agent
│   │   ├── memory.py      # Conversation memory
│   │   ├── tools.py       # Agent tools/functions
│   │   └── prompts.py     # Prompt templates
│   ├── storage/           # Data persistence
│   │   ├── db_models.py   # SQLAlchemy models
│   │   └── repository.py  # CRUD operations
│   ├── api/               # REST API
│   │   └── app.py         # FastAPI application
│   ├── config.py          # Configuration management
│   ├── pipeline.py        # Orchestration pipeline
│   └── logging_config.py  # Structured logging
├── cli/
│   └── main.py            # CLI interface
├── tests/
│   ├── unit/              # Unit tests per module
│   ├── integration/       # Cross-module tests
│   └── system/            # End-to-end tests
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── AI_WORKFLOW.md
└── README.md
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run only unit tests
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run system tests
pytest tests/system/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_scraper/test_models.py -v
```

## Design Decisions

1. **Async-first**: All I/O operations are async for performance
2. **Mock scraper**: Enables full development/testing without TikTok access
3. **Modular pipeline**: Each stage is independently testable
4. **Tool-augmented agent**: Uses Claude's tool use for structured reasoning
5. **Sliding window memory**: Efficient conversation context management
6. **SQLite default**: Zero-config local storage, production-ready with PostgreSQL

## License

MIT License

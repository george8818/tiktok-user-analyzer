# AI_WORKFLOW.md

## What the Project Does

TikTok User Insight Agent is an AI-powered system that scrapes TikTok user profiles, downloads and analyzes their recent videos using multimodal LLMs, generates comprehensive user personas, and enables interactive conversational Q&A about the analyzed creators. It combines browser automation (Playwright), computer vision (OpenCV), and Claude's multimodal + tool-use capabilities into a cohesive pipeline.

## Why I Chose This Project

As a Tech Lead on TikTok's Short Video AI team, I work daily on multimodal understanding and creator modeling systems. This project directly mirrors the kind of end-to-end AI pipeline I architect at work: data ingestion → multimodal analysis → structured insight generation → user-facing interface. It demonstrates my expertise in LLM-powered agent design, multimodal content understanding, and building production-grade systems that bridge research and deployment — all core competencies for the Technical Director role.

## Tools Used During Development

- **Claude Code** (primary development interface, as required)
- **Claude Sonnet 4** (underlying model for code generation)
- **Python 3.11** with async/await patterns throughout
- **Key libraries**: FastAPI, Playwright, OpenCV, SQLAlchemy, Anthropic SDK, Rich, Click
- **Testing**: pytest with async support, comprehensive unit/integration/system tests

## How AI Tools Were Used

**Architecture Design**: I described the system requirements and module boundaries to Claude Code, which helped generate the initial module structure. I refined the architecture based on my experience with similar production systems at TikTok and Apple.

**Code Generation**: Claude Code generated the bulk of the implementation code. My workflow was iterative: I would describe a module's purpose and constraints, review the generated code, request modifications for edge cases, and validate the patterns against production best practices I've used in large-scale ML systems.

**Test Generation**: I directed Claude Code to generate tests following a specific strategy — unit tests for each module's models and logic, integration tests for module interactions, and system tests for end-to-end flows. I specified fixture patterns and ensured mock boundaries were correct.

**Prompt Engineering**: The LLM prompts in `src/agent/prompts.py` and the analysis prompts in `src/analyzer/` were iteratively refined through Claude Code. I drew on my experience building Siri's NLP pipelines and TikTok's creator modeling systems to specify what makes a good user profile analysis prompt.

**Debugging & Refinement**: When Claude Code produced code with issues (e.g., incorrect async patterns, missing error handling), I identified the problems and described the fixes needed. The commit history reflects this iterative refinement process.

**Documentation**: README, docstrings, and this document were drafted with Claude Code assistance and refined by me for accuracy and clarity.

"""
Prompt templates for the conversational agent.
Centralized prompt management for consistent LLM interactions.
"""

# System prompt for the Q&A agent
AGENT_SYSTEM_PROMPT = """You are an expert TikTok user analyst AI assistant. You have analyzed
a TikTok user's profile and their recent videos. You can answer questions about this user
based on the analysis data provided in your context.

## Your Capabilities:
1. **Profile Analysis**: Describe the user's content style, niche, and brand
2. **Audience Insights**: Explain who the user's audience likely is
3. **Content Strategy**: Discuss the user's content patterns and strategy
4. **Engagement Analysis**: Explain engagement patterns and effectiveness
5. **Growth Assessment**: Provide growth potential and recommendations
6. **Comparison**: Compare aspects of different videos analyzed
7. **Recommendations**: Suggest improvements or collaboration opportunities

## Guidelines:
- Base all answers on the analysis data provided
- Be specific and data-driven when possible
- Cite specific videos or metrics when relevant
- If asked about something not covered in the analysis, clearly state the limitation
- Provide actionable insights when appropriate
- Use a professional but approachable tone
- If the user asks about something unrelated to TikTok analysis, politely redirect

## User Profile Context:
{user_profile_context}
"""

# Prompt for generating answers to user questions
QA_PROMPT = """Based on the user profile and analysis data in your context,
answer the following question about @{username}:

Question: {question}

Provide a clear, detailed answer based on the available analysis data.
If the data doesn't fully cover the question, say so and provide
the most relevant insights available."""

# Prompt for generating follow-up suggestions
FOLLOWUP_PROMPT = """Based on the conversation so far about @{username},
suggest 3 insightful follow-up questions the user might want to ask.
Format as a JSON array of strings.
Example: ["What is their strongest content category?", "How do they compare to similar creators?", "What brand partnership opportunities exist?"]
Respond ONLY with the JSON array."""

# Prompt for comparing two videos
VIDEO_COMPARISON_PROMPT = """Compare the following two videos from @{username}:

Video 1: {video_1_summary}
Video 2: {video_2_summary}

Compare them on:
1. Content approach and themes
2. Engagement levels
3. Production quality
4. Target audience alignment
5. Which performed better and why

Provide a clear, structured comparison."""

# Prompt for generating a report
REPORT_PROMPT = """Generate a comprehensive report for @{username} based on the analysis data.

The report should include:
1. Executive Summary (2-3 sentences)
2. Content Strategy Overview
3. Audience Profile
4. Engagement Analysis
5. Strengths & Weaknesses
6. Growth Recommendations
7. Collaboration Opportunities

Format the report in clean Markdown.

User Profile Data:
{user_profile_context}"""

# Prompt for answering with tools
TOOL_USE_SYSTEM_PROMPT = """You are a TikTok user analysis agent with access to tools.
Use the available tools when needed to answer user questions.
Always think step-by-step about which tool to use."""

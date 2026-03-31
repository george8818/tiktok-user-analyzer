"""
Demo script: shows the full pipeline flow without needing an API key.
Demonstrates scraping → analysis → profile → agent interaction.
"""
import asyncio
import json
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from src.scraper.tiktok_scraper import MockTikTokScraper
from src.analyzer.models import (
    UserProfile, VideoAnalysisResult, ContentPattern,
    AudienceSegment, BrandPersonality,
)
from src.agent.memory import ConversationMemory

console = Console()

async def main():
    # =========================================================
    # STEP 1: Scrape TikTok User (Mock)
    # =========================================================
    console.print(Panel(
        "[bold yellow]STEP 1: Scraping TikTok User Profile[/bold yellow]",
        border_style="yellow",
    ))

    username = "fitness_sarah"
    scraper = MockTikTokScraper()
    async with scraper:
        scraped = await scraper.scrape_user(username, max_videos=2)

    user = scraped.user
    console.print(f"\n[green]✓ Profile scraped successfully![/green]")
    console.print(f"  Username: @{user.username}")
    console.print(f"  Display Name: {user.display_name}")
    console.print(f"  Bio: {user.bio}")
    console.print(f"  Followers: {user.stats.followers:,}")
    console.print(f"  Following: {user.stats.following:,}")
    console.print(f"  Total Likes: {user.stats.likes:,}")
    console.print(f"  Videos Found: {len(user.videos)}")

    console.print(f"\n[bold]Scraped Videos:[/bold]")
    for i, video in enumerate(user.videos, 1):
        console.print(f"\n  [cyan]Video {i}:[/cyan]")
        console.print(f"    ID: {video.video_id}")
        console.print(f"    Description: {video.description[:80]}...")
        console.print(f"    Hashtags: {', '.join('#'+h for h in video.hashtags)}")
        console.print(f"    Views: {video.stats.views:,} | Likes: {video.stats.likes:,}")
        console.print(f"    Engagement: {video.stats.engagement_summary}")
        console.print(f"    Duration: {video.duration_seconds}s")

    # =========================================================
    # STEP 2: Video Analysis (simulated LLM output)
    # =========================================================
    console.print(Panel(
        "[bold yellow]STEP 2: Analyzing Videos with Claude Vision API[/bold yellow]\n"
        "[dim](In production, this sends video frames to Claude's multimodal API)[/dim]",
        border_style="yellow",
    ))

    # Simulate what the LLM would return
    video_analyses = [
        VideoAnalysisResult(
            video_id=user.videos[0].video_id,
            video_url=user.videos[0].url,
            content_summary="A day-in-the-life vlog showing the creator's daily routine in San Francisco, including morning coding sessions, afternoon coffee runs, and evening workouts.",
            content_category="lifestyle/tech",
            content_subcategories=["day-in-my-life", "tech-life", "vlog"],
            content_themes=["work-life balance", "tech career", "San Francisco living"],
            production_quality="semi-professional",
            editing_style="Quick cuts with text overlays, transitions synced to music",
            visual_aesthetic="Clean, bright, modern aesthetic",
            music_mood="Chill lo-fi, upbeat",
            has_voiceover=True,
            target_audience="Young professionals 22-35 in tech",
            tone="casual, aspirational",
            engagement_hooks=["relatable morning routine", "aesthetic desk setup reveal", "food content interlude"],
            call_to_action="Follow for more tech life content",
            description=user.videos[0].description,
            hashtags=user.videos[0].hashtags,
            views=user.videos[0].stats.views,
            likes=user.videos[0].stats.likes,
            comments=user.videos[0].stats.comments,
        ),
        VideoAnalysisResult(
            video_id=user.videos[1].video_id,
            video_url=user.videos[1].url,
            content_summary="A cooking video where the creator attempts a viral TikTok pasta recipe, with humorous commentary and a taste-test reaction at the end.",
            content_category="food/entertainment",
            content_subcategories=["cooking", "viral-recipe", "reaction"],
            content_themes=["viral food trends", "home cooking", "entertainment"],
            production_quality="casual",
            editing_style="Step-by-step with reaction shots, text captions",
            visual_aesthetic="Warm kitchen setting, close-up food shots",
            music_mood="Upbeat, playful",
            has_voiceover=True,
            target_audience="Gen Z and young millennials interested in food and trends",
            tone="humorous, enthusiastic",
            engagement_hooks=["viral recipe promise", "taste test suspense", "relatable cooking fails"],
            description=user.videos[1].description,
            hashtags=user.videos[1].hashtags,
            views=user.videos[1].stats.views,
            likes=user.videos[1].stats.likes,
            comments=user.videos[1].stats.comments,
        ),
    ]

    for va in video_analyses:
        console.print(f"\n[green]✓ Video {va.video_id} analyzed[/green]")
        console.print(f"  Category: {va.content_category}")
        console.print(f"  Summary: {va.content_summary[:100]}...")
        console.print(f"  Tone: {va.tone}")
        console.print(f"  Target: {va.target_audience}")

    # =========================================================
    # STEP 3: Generate User Profile (simulated LLM output)
    # =========================================================
    console.print(Panel(
        "[bold yellow]STEP 3: Generating User Profile with Claude[/bold yellow]\n"
        "[dim](In production, this synthesizes all analysis into a structured profile)[/dim]",
        border_style="yellow",
    ))

    profile = UserProfile(
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        profile_summary=(
            f"@{user.username} is a versatile content creator based in the US who blends "
            "tech career lifestyle content with viral food and trend participation. With 1.5M "
            "followers, they've built a loyal audience of young professionals who relate to their "
            "authentic portrayal of work-life balance in the tech industry. Their content strategy "
            "alternates between aspirational day-in-my-life vlogs and lighter entertainment content, "
            "creating a well-rounded creator brand that appeals to both career-focused viewers and "
            "casual trend followers."
        ),
        creator_type="lifestyle/tech hybrid",
        niche="tech professional lifestyle",
        estimated_influence_tier="macro",
        primary_topics=["tech career", "day-in-my-life", "cooking", "San Francisco", "work-life balance"],
        content_format="Short-form vlogs (30-60s) with text overlays and trending audio",
        posting_style="Mix of planned lifestyle content and spontaneous trend participation",
        content_patterns=[
            ContentPattern(
                pattern_type="theme",
                description="Alternates between career-focused content and lighter food/trend videos",
                frequency="Regular pattern across posts",
                examples=["tech vlog → cooking video → tech vlog"],
            ),
            ContentPattern(
                pattern_type="engagement",
                description="Uses relatable hooks in first 3 seconds to retain viewers",
                frequency="Every video",
                examples=["'POV: you...' openings", "aesthetic reveals"],
            ),
            ContentPattern(
                pattern_type="format",
                description="Consistent use of lo-fi music, text overlays, and quick cuts",
                frequency="Signature style across all content",
                examples=["Text captions on every clip", "Music-synced transitions"],
            ),
        ],
        audience_segments=[
            AudienceSegment(
                segment_name="Young Tech Professionals",
                age_range="22-32",
                interests=["tech careers", "productivity", "startup culture"],
                engagement_level="high",
                description="Software engineers and tech workers who see themselves in the creator's content",
            ),
            AudienceSegment(
                segment_name="Aspirational Students",
                age_range="18-24",
                interests=["career goals", "lifestyle", "study motivation"],
                engagement_level="high",
                description="College students and recent grads aspiring to tech careers",
            ),
            AudienceSegment(
                segment_name="Casual Trend Followers",
                age_range="16-28",
                interests=["viral trends", "food", "entertainment"],
                engagement_level="medium",
                description="Viewers drawn to viral content who stay for personality",
            ),
        ],
        primary_audience_description="Young tech professionals and aspiring students aged 18-32",
        brand_personality=BrandPersonality(
            primary_archetype="The Creator",
            secondary_archetype="The Everyperson",
            tone_of_voice="Casual, authentic, subtly aspirational",
            values=["authenticity", "work-life balance", "continuous learning", "community"],
            differentiators=["Tech insider perspective with mass appeal", "Relatable despite success", "Diverse content range"],
        ),
        engagement_strategy="Hooks viewers with relatable scenarios, retains with quality editing and authentic personality",
        community_building="Active comment section engagement, relatable content that sparks conversation",
        growth_potential="Strong potential — could expand into long-form YouTube, brand partnerships with tech companies, or launch a personal brand/course",
        strengths=[
            "Authentic, relatable persona that builds trust",
            "High production quality for the niche",
            "Diverse content keeps audience engaged",
            "Strong engagement rates across videos",
            "Well-defined visual and editing style",
        ],
        areas_for_improvement=[
            "Could benefit from more consistent posting schedule",
            "Niche could be sharpened — risk of being too broad",
            "Limited use of series/recurring formats for retention",
            "Could leverage more community features (Lives, Q&As)",
        ],
        collaboration_opportunities=["Tech companies (laptops, monitors, dev tools)", "Food/meal kit brands", "Productivity apps", "Coworking spaces", "Online education platforms"],
        videos_analyzed=2,
        video_analyses=video_analyses,
        generated_at=datetime.utcnow(),
        confidence_score=0.82,
    )

    # Display profile
    console.print(f"\n[green]✓ Profile generated! Confidence: {profile.confidence_score:.0%}[/green]\n")

    table = Table(title=f"User Profile: @{profile.username}", show_lines=True)
    table.add_column("Field", style="bold cyan", width=20)
    table.add_column("Value", width=80)
    table.add_row("Creator Type", profile.creator_type)
    table.add_row("Niche", profile.niche)
    table.add_row("Influence Tier", profile.estimated_influence_tier)
    table.add_row("Topics", ", ".join(profile.primary_topics))
    table.add_row("Content Format", profile.content_format)
    table.add_row("Brand Archetype", f"{profile.brand_personality.primary_archetype} / {profile.brand_personality.secondary_archetype}")
    table.add_row("Tone", profile.brand_personality.tone_of_voice)
    table.add_row("Strengths", "\n".join(f"✓ {s}" for s in profile.strengths))
    table.add_row("Improvement", "\n".join(f"→ {a}" for a in profile.areas_for_improvement))
    console.print(table)

    console.print(Panel(profile.profile_summary, title="Profile Summary", border_style="green"))

    # =========================================================
    # STEP 4: Agent Q&A (simulated)
    # =========================================================
    console.print(Panel(
        "[bold yellow]STEP 4: Interactive Agent Q&A[/bold yellow]\n"
        "[dim](In production, each question is sent to Claude with the full profile as context.\n"
        "The agent uses tool-augmented reasoning to answer.)[/dim]",
        border_style="yellow",
    ))

    # Show what the agent system prompt looks like
    context = profile.to_context_string()
    console.print(f"[dim]Agent context loaded: {len(context)} characters of structured profile data[/dim]\n")

    # Simulate Q&A pairs
    qa_pairs = [
        (
            "这个用户主要做什么类型的内容？",
            f"@{profile.username} 是一个 **lifestyle/tech hybrid** 类型的创作者，主要制作两类内容：\n\n"
            "1. **科技职场生活**：以 day-in-my-life 的形式展示作为科技从业者的日常，包括编程、咖啡时间、健身等。这类内容面向22-32岁的科技行业从业者。\n\n"
            "2. **美食和潮流内容**：参与TikTok上的病毒式挑战和热门食谱，风格轻松幽默。\n\n"
            f"他们的内容策略是在这两种类型之间交替发布，保持受众的多样性和参与度。视频通常在30-60秒之间，使用 lo-fi 音乐、文字覆盖和快速剪辑的标志性风格。"
        ),
        (
            "他的受众群体是怎样的？",
            f"根据分析，@{profile.username} 有三个主要受众群体：\n\n"
            "**1. 年轻科技从业者 (22-32岁)** — 参与度最高\n"
            "   软件工程师和科技工作者，在创作者的内容中看到自己的影子。对科技职业、效率工具和创业文化感兴趣。\n\n"
            "**2. 有志向的学生 (18-24岁)** — 参与度高\n"
            "   大学生和应届毕业生，以科技职业为目标。被创作者的生活方式所吸引和激励。\n\n"
            "**3. 休闲潮流关注者 (16-28岁)** — 参与度中等\n"
            "   被病毒式内容吸引进来，因为创作者的个性而留下。\n\n"
            f"总体来说，核心受众是 **18-32岁的年轻科技专业人士和有志学生**。"
        ),
        (
            "两个视频对比一下，哪个表现更好？",
            f"让我对比两个分析过的视频：\n\n"
            f"**视频 1** (科技日常 vlog):\n"
            f"  - 观看: 300,000 | 点赞: 45,000 | 评论: 1,500\n"
            f"  - 互动率: Very High (14.8%)\n"
            f"  - 类别: lifestyle/tech | 语气: casual, aspirational\n\n"
            f"**视频 2** (病毒式食谱):\n"
            f"  - 观看: 150,000 | 点赞: 21,000 | 评论: 450\n"
            f"  - 互动率: Very High (14.8%)\n"
            f"  - 类别: food/entertainment | 语气: humorous, enthusiastic\n\n"
            f"**结论**: 视频1在绝对数字上表现更好（观看量高2倍），但两者的互动率相近。这表明科技生活内容是该创作者的核心竞争力，能吸引更多精准受众；而美食内容虽然覆盖面稍窄，但同样能维持高参与度，说明创作者的个人魅力是跨品类的。"
        ),
        (
            "你觉得什么品牌合作最适合这个创作者？",
            f"基于 @{profile.username} 的内容风格和受众特征，我推荐以下品牌合作方向：\n\n"
            "**最匹配 (高相关性)**:\n"
            "• **科技硬件品牌** — 笔记本电脑、显示器、机械键盘（如Apple、Dell、Logitech）。桌面setup是内容核心元素。\n"
            "• **开发者工具** — IDE、云服务、效率工具（如JetBrains、Notion、Vercel）。受众精准匹配。\n\n"
            "**强匹配**:\n"
            "• **食品/餐饮品牌** — 速食品牌、咖啡品牌、meal kit服务。美食内容有数据支撑。\n"
            "• **效率/生活方式App** — 日程管理、健身追踪、冥想类（如Headspace、Strava）。\n\n"
            "**增长机会**:\n"
            "• **在线教育平台** — 编程课程、技能学习平台（如Coursera、Udemy）。学生受众是变现潜力。\n"
            "• **共享办公空间** — WeWork等品牌与创作者展示的生活方式高度契合。"
        ),
    ]

    for question, answer in qa_pairs:
        console.print(f"\n[bold cyan]You:[/bold cyan] {question}")
        console.print(f"\n[bold green]Agent:[/bold green] {answer}")
        console.print("[dim]" + "─" * 80 + "[/dim]")

    # =========================================================
    # Show how it works in production
    # =========================================================
    console.print(Panel(
        "[bold yellow]实际使用方式[/bold yellow]\n\n"
        "[white]# 1. 设置 API Key[/white]\n"
        "cp .env.example .env\n"
        "# 编辑 .env 填入 ANTHROPIC_API_KEY=sk-ant-xxx\n\n"
        "[white]# 2. Mock模式 (不需要爬TikTok，演示用)[/white]\n"
        "python -m cli.main analyze @any_username --mock --chat\n\n"
        "[white]# 3. 真实模式 (爬取真实TikTok数据)[/white]\n"
        "playwright install chromium  # 首次需安装浏览器\n"
        "python -m cli.main analyze @charlidamelio --chat\n\n"
        "[white]# 4. API模式[/white]\n"
        "python -m cli.main serve\n"
        'curl -X POST http://localhost:8000/api/v1/analyze -d \'{"username":"charlidamelio","use_mock":true}\'\n'
        'curl -X POST http://localhost:8000/api/v1/chat/charlidamelio -d \'{"message":"这个用户主要做什么？"}\'',
        border_style="blue",
    ))

asyncio.run(main())

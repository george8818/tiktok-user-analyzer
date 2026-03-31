"""
CLI interface for TikTok User Analyzer.

Provides command-line access to:
- Analyze TikTok users
- Interactive Q&A chat
- View cached profiles
- Generate reports
- Start the API server
"""

import asyncio
import sys
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import Settings, get_settings
from src.logging_config import setup_logging
from src.pipeline import AnalysisPipeline

console = Console()


def run_async(coro):
    """Helper to run async functions from sync CLI commands."""
    return asyncio.get_event_loop().run_until_complete(coro)


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx, debug: bool):
    """TikTok User Analyzer - AI-powered user profiling agent."""
    ctx.ensure_object(dict)
    settings = get_settings()
    if debug:
        settings.logging.level = "DEBUG"
    setup_logging(
        level=settings.logging.level,
        log_format="console",
    )
    ctx.obj["settings"] = settings


@cli.command()
@click.argument("username")
@click.option("--max-videos", "-n", default=2, help="Max videos to analyze (1-5)")
@click.option("--mock", is_flag=True, help="Use mock data for testing")
@click.option("--chat", is_flag=True, help="Start interactive chat after analysis")
@click.pass_context
def analyze(ctx, username: str, max_videos: int, mock: bool, chat: bool):
    """Analyze a TikTok user's profile and content."""
    settings = ctx.obj["settings"]

    console.print(Panel(
        f"[bold blue]Analyzing @{username.lstrip('@')}[/bold blue]\n"
        f"Max videos: {max_videos} | Mock: {mock}",
        title="TikTok User Analyzer",
    ))

    async def _analyze():
        pipeline = AnalysisPipeline(settings)
        await pipeline.initialize()

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Scraping user profile...", total=None)

                profile = await pipeline.analyze_user(
                    username=username,
                    max_videos=max_videos,
                    use_mock=mock,
                )

                progress.update(task, description="Analysis complete!")

            # Display results
            _display_profile(profile)

            if chat:
                agent = pipeline.create_agent(profile)
                await _interactive_chat(agent, username)

        finally:
            await pipeline.close()

    run_async(_analyze())


@cli.command()
@click.argument("username")
@click.pass_context
def chat_cmd(ctx, username: str):
    """Start interactive chat about a previously analyzed user."""
    settings = ctx.obj["settings"]

    async def _chat():
        pipeline = AnalysisPipeline(settings)
        await pipeline.initialize()

        try:
            profile = await pipeline._repo.get_profile(username.lstrip("@"))
            if not profile:
                console.print(
                    f"[red]Profile not found for @{username}. "
                    f"Run 'analyze {username}' first.[/red]"
                )
                return

            console.print(f"[green]Profile loaded for @{profile.username}[/green]")
            agent = pipeline.create_agent(profile)
            await _interactive_chat(agent, profile.username)

        finally:
            await pipeline.close()

    run_async(_chat())


@cli.command(name="list")
@click.pass_context
def list_profiles(ctx):
    """List all analyzed profiles."""
    settings = ctx.obj["settings"]

    async def _list():
        pipeline = AnalysisPipeline(settings)
        await pipeline.initialize()

        try:
            profiles = await pipeline.get_cached_profiles()

            if not profiles:
                console.print("[yellow]No profiles found. Run 'analyze' first.[/yellow]")
                return

            table = Table(title="Analyzed Profiles")
            table.add_column("Username", style="cyan")
            table.add_column("Creator Type", style="green")
            table.add_column("Niche")
            table.add_column("Videos", justify="right")
            table.add_column("Confidence", justify="right")
            table.add_column("Updated")

            for p in profiles:
                table.add_row(
                    f"@{p['username']}",
                    p.get("creator_type", ""),
                    p.get("niche", ""),
                    str(p.get("videos_analyzed", 0)),
                    f"{p.get('confidence_score', 0):.0%}",
                    p.get("updated_at", "")[:10] if p.get("updated_at") else "",
                )

            console.print(table)

        finally:
            await pipeline.close()

    run_async(_list())


@cli.command()
@click.argument("username")
@click.option("--output", "-o", default=None, help="Output file path")
@click.pass_context
def report(ctx, username: str, output: Optional[str]):
    """Generate a report for an analyzed user."""
    settings = ctx.obj["settings"]

    async def _report():
        pipeline = AnalysisPipeline(settings)
        await pipeline.initialize()

        try:
            profile = await pipeline._repo.get_profile(username.lstrip("@"))
            if not profile:
                console.print(f"[red]Profile not found: @{username}[/red]")
                return

            agent = pipeline.create_agent(profile)

            with console.status("Generating report..."):
                report_md = await agent.generate_report()

            if output:
                with open(output, "w") as f:
                    f.write(report_md)
                console.print(f"[green]Report saved to {output}[/green]")
            else:
                console.print(Markdown(report_md))

        finally:
            await pipeline.close()

    run_async(_report())


@cli.command()
@click.option("--host", default="0.0.0.0", help="API host")
@click.option("--port", default=8000, help="API port")
@click.pass_context
def serve(ctx, host: str, port: int):
    """Start the API server."""
    import uvicorn

    console.print(Panel(
        f"[bold green]Starting API server[/bold green]\n"
        f"http://{host}:{port}\n"
        f"Docs: http://{host}:{port}/docs",
        title="TikTok User Analyzer API",
    ))

    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        reload=ctx.obj["settings"].api.debug,
    )


def _display_profile(profile):
    """Display a user profile in the terminal."""
    console.print()
    console.print(Panel(
        f"[bold]@{profile.username}[/bold] ({profile.display_name})\n"
        f"[dim]{profile.bio}[/dim]",
        title="User Profile",
        border_style="blue",
    ))

    # Summary
    console.print(Panel(
        profile.profile_summary,
        title="Profile Summary",
        border_style="green",
    ))

    # Quick stats table
    table = Table(show_header=False, box=None)
    table.add_column("Label", style="bold")
    table.add_column("Value")
    table.add_row("Creator Type", profile.creator_type)
    table.add_row("Niche", profile.niche)
    table.add_row("Influence Tier", profile.estimated_influence_tier)
    table.add_row("Content Format", profile.content_format)
    table.add_row("Videos Analyzed", str(profile.videos_analyzed))
    table.add_row("Confidence", f"{profile.confidence_score:.0%}")
    table.add_row("Topics", ", ".join(profile.primary_topics))

    console.print(table)

    # Strengths
    if profile.strengths:
        console.print("\n[bold green]Strengths:[/bold green]")
        for s in profile.strengths:
            console.print(f"  ✓ {s}")

    # Areas for improvement
    if profile.areas_for_improvement:
        console.print("\n[bold yellow]Areas for Improvement:[/bold yellow]")
        for a in profile.areas_for_improvement:
            console.print(f"  → {a}")

    console.print()


async def _interactive_chat(agent, username: str):
    """Run an interactive chat session."""
    console.print(Panel(
        f"[bold]Interactive Q&A about @{username}[/bold]\n"
        f"Type your questions below. Type 'exit' or 'quit' to end.\n"
        f"Type 'suggest' for follow-up suggestions.\n"
        f"Type 'report' to generate a full report.",
        title="Chat Mode",
        border_style="cyan",
    ))

    while True:
        try:
            question = Prompt.ask("\n[bold cyan]You[/bold cyan]")

            if question.lower() in ("exit", "quit", "q"):
                console.print("[dim]Chat ended.[/dim]")
                break

            if question.lower() == "suggest":
                suggestions = await agent.get_follow_up_suggestions()
                console.print("\n[bold]Suggested questions:[/bold]")
                for i, s in enumerate(suggestions, 1):
                    console.print(f"  {i}. {s}")
                continue

            if question.lower() == "report":
                with console.status("Generating report..."):
                    report_text = await agent.generate_report()
                console.print(Markdown(report_text))
                continue

            if not question.strip():
                continue

            with console.status("Thinking..."):
                response = await agent.chat(question)

            console.print(f"\n[bold green]Agent[/bold green]: {response}")

        except KeyboardInterrupt:
            console.print("\n[dim]Chat ended.[/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")


if __name__ == "__main__":
    cli()

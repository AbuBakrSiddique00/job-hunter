import asyncio
import logging
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def cli(verbose: bool):
    """🎯 Job Hunter Agent - AI-powered job discovery and application."""
    setup_logging(verbose)

@cli.command()
def run():
    """Start the Job Hunter agent (scrape + score + Telegram bot)."""
    from job_hunter.engine import JobHunterEngine
    console.print(Panel.fit("[bold green]🚀 Starting Job Hunter Agent[/]", border_style="green"))
    engine = JobHunterEngine()
    try:
        asyncio.run(engine.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/]")
        asyncio.run(engine.shutdown())

@cli.command()
def scrape():
    """Run a one-time scrape cycle without starting the bot."""
    from job_hunter.engine import JobHunterEngine
    console.print("[cyan]Running one-time scrape cycle...[/]")
    engine = JobHunterEngine()
    async def _run():
        await engine.db.connect()
        await engine.run_scrape_cycle()
        await engine.shutdown()
    asyncio.run(_run())

@cli.command()
def stats():
    """Show job discovery statistics."""
    from job_hunter.db.database import Database
    from job_hunter.config import settings
    async def _stats():
        db = Database(settings.db_path)
        await db.connect()
        s = await db.get_stats()
        await db.close()
        table = Table(title="📊 Job Hunter Statistics")
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="green", justify="right")
        for k, v in s.items():
            table.add_row(k.replace("_", " ").title(), str(v))
        console.print(table)
    asyncio.run(_stats())

@cli.command()
def profile():
    """Show current user profile."""
    from job_hunter.profile import load_profile
    p = load_profile()
    console.print(Panel.fit(f"[bold]{p.name}[/]\n{p.bio}", title="👤 Profile"))
    console.print(f"Target: {', '.join(p.target_titles)}")
    console.print(f"Skills: {', '.join(p.skills)}")
    console.print(f"Experience: {p.experience_years} years")
    console.print(f"Remote only: {p.remote_only}")
    if p.min_salary:
        console.print(f"Min salary: ${p.min_salary:,}")

if __name__ == "__main__":
    cli()

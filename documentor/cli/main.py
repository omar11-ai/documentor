"""Main CLI entry point for DocuMentor."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from documentor.core.config import Config, get_config, set_config
from documentor.core.logging import setup_logging, get_logger
from documentor.core.exceptions import DocumentorError
from documentor.analysis.analyzer import CodebaseAnalyzer
from documentor.generation.generator import DocumentationGenerator
from documentor.generation.model_client import ModelRouter

app = typer.Typer(
    name="documentor",
    help="AI-powered contextual documentation assistant for codebases",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()
logger = get_logger(__name__)


def _setup(log_level: str = "INFO") -> None:
    """Setup logging and config."""
    setup_logging(log_level)


@app.callback()
def callback(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """DocuMentor - AI-powered contextual documentation assistant."""
    _setup("DEBUG" if verbose else "INFO")

    if config_path:
        config = Config.load(config_path)
        set_config(config)
    else:
        # Ensure config is loaded
        get_config()


@app.command()
def init(
    path: Path = typer.Argument(Path.cwd(), help="Project directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
):
    """Initialize DocuMentor configuration in a project."""
    config_path = path / ".documentor.yaml"

    if config_path.exists() and not force:
        console.print(f"[yellow]Config already exists at {config_path}. Use --force to overwrite.[/yellow]")
        raise typer.Exit(1)

    config = Config.create_default(config_path)
    console.print(f"[green]Created config at {config_path}[/green]")
    console.print("\nEdit the config file to customize:")
    console.print("  - Project name and languages")
    console.print("  - Include/exclude patterns")
    console.print("  - Model preferences (local vs cloud)")
    console.print("  - Nebius API credentials")


@app.command()
def analyze(
    path: Path = typer.Argument(Path.cwd(), help="Project directory"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save knowledge graph to file"),
):
    """Analyze codebase and build knowledge graph."""
    _setup()

    try:
        console.print("[cyan]Analyzing codebase...[/cyan]")
        analyzer = CodebaseAnalyzer(path)
        result = analyzer.analyze()
        console.print("[green]Analysis complete![/green]")

        # Display results
        table = Table(title="Analysis Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Files analyzed", str(result.files_analyzed))
        table.add_row("Entities found", str(result.entities_found))
        table.add_row("Languages", ", ".join(l.value for l in result.languages_detected))
        table.add_row("Errors", str(len(result.errors)))
        console.print(table)

        if result.errors:
            console.print("\n[red]Errors:[/red]")
            for err in result.errors:
                console.print(f"  - {err}")

        if output:
            import json
            output.write_text(json.dumps(result.graph.to_dict(), indent=2))
            console.print(f"\n[green]Knowledge graph saved to {output}[/green]")

    except DocumentorError as e:
        console.print(f"[red]Error: {e.message}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        logger.exception("Analysis failed")
        raise typer.Exit(1)


@app.command()
def generate(
    path: Path = typer.Argument(Path.cwd(), help="Project directory"),
    output: Path = typer.Option(Path("docs"), "--output", "-o", help="Output directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing docs"),
):
    """Generate documentation from analyzed codebase."""
    _setup()

    if output.exists() and not force:
        console.print(f"[yellow]Output directory {output} exists. Use --force to overwrite.[/yellow]")
        raise typer.Exit(1)

    try:
        console.print("[cyan]Analyzing codebase...[/cyan]")
        analyzer = CodebaseAnalyzer(path)
        result = analyzer.analyze()
        console.print("[green]Analysis complete[/green]")

        console.print("[cyan]Generating documentation...[/cyan]")
        generator = DocumentationGenerator(result.graph)
        gen_result = generator.generate_all(output)
        console.print("[green]Generation complete![/green]")

        # Display results
        table = Table(title="Generation Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Modules documented", str(gen_result.stats["modules_documented"]))
        table.add_row("Entities documented", str(gen_result.stats["entities_documented"]))
        table.add_row("LLM docs", str(gen_result.stats.get("llm_docs", 0)))
        table.add_row("Offline fallback docs", str(gen_result.stats.get("fallback_docs", 0)))
        table.add_row("Output directory", str(output))
        table.add_row("Errors", str(gen_result.stats["errors"]))
        console.print(table)

        if gen_result.errors:
            console.print("\n[red]Errors:[/red]")
            for err in gen_result.errors[:10]:
                console.print(f"  - {err}")

        console.print(f"\n[green]Documentation generated in {output}/[/green]")
        console.print("Run [cyan]documentor serve[/cyan] to browse locally")

    except DocumentorError as e:
        console.print(f"[red]Error: {e.message}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        logger.exception("Generation failed")
        raise typer.Exit(1)


@app.command()
def watch(
    path: Path = typer.Argument(Path.cwd(), help="Project directory"),
    output: Path = typer.Option(Path("docs"), "--output", "-o", help="Output directory"),
    interval: float = typer.Option(2.0, "--interval", help="Poll interval in seconds"),
    once: bool = typer.Option(False, "--once", help="Run once and exit (useful for CI)"),
):
    """Watch for changes and regenerate docs incrementally (polling)."""
    _setup()
    import time
    import hashlib

    def _snapshot(root: Path) -> str:
        h = hashlib.sha256()
        for p in sorted(root.rglob("*.py")):
            if ".git" in p.parts or "__pycache__" in p.parts:
                continue
            try:
                h.update(str(p.relative_to(root)).encode())
                h.update(str(p.stat().st_mtime).encode())
                h.update(str(p.stat().st_size).encode())
            except OSError:
                continue
        return h.hexdigest()

    console.print(f"[cyan]Watching {path} (poll every {interval}s). Press Ctrl+C to stop.[/cyan]")
    last = _snapshot(path)
    try:
        while True:
            analyzer = CodebaseAnalyzer(path)
            result = analyzer.analyze()
            generator = DocumentationGenerator(result.graph)
            gen_result = generator.generate_all(output)
            console.print(
                f"[green]Regenerated:[/green] {gen_result.stats['entities_documented']} entities, "
                f"{gen_result.stats.get('fallback_docs', 0)} offline, "
                f"{gen_result.stats.get('llm_docs', 0)} LLM, "
                f"{gen_result.stats['errors']} errors"
            )
            if once:
                break
            time.sleep(interval)
            current = _snapshot(path)
            if current == last:
                # No changes; avoid redundant regen next loop by waiting again
                time.sleep(interval)
                current = _snapshot(path)
                if current == last:
                    continue
            last = current
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch stopped[/yellow]")


@app.command()
def serve(
    path: Path = typer.Argument(Path.cwd(), help="Project directory"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to bind"),
    docs_dir: Path = typer.Option(Path("docs"), "--docs", "-d", help="Documentation directory"),
):
    """Start local web server to browse documentation."""
    _setup()

    if not docs_dir.exists():
        console.print(f"[red]Documentation directory {docs_dir} not found. Run 'documentor generate' first.[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Starting server at http://{host}:{port}[/green]")
    console.print("Press Ctrl+C to stop")

    try:
        from documentor.server.app import create_app
        import uvicorn

        app = create_app(docs_dir)
        uvicorn.run(app, host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Server error: {e}[/red]")
        logger.exception("Server failed")
        raise typer.Exit(1)


@app.command()
def status(
    path: Path = typer.Argument(Path.cwd(), help="Project directory"),
):
    """Show project status."""
    _setup()

    config = get_config()
    docs_dir = path / "docs"
    cache_dir = config.cache.directory

    table = Table(title="DocuMentor Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")

    table.add_row("Config", "[OK] Loaded" if (path / ".documentor.yaml").exists() else "[MISSING]")
    table.add_row("Cache dir", str(cache_dir) + (" [OK]" if cache_dir.exists() else " [MISSING]"))
    table.add_row("Docs dir", str(docs_dir) + (" [OK]" if docs_dir.exists() else " [MISSING]"))
    table.add_row("Git repo", "[OK]" if (path / ".git").exists() else "[MISSING]")

    console.print(table)


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    edit: bool = typer.Option(False, "--edit", help="Open config in editor"),
):
    """Manage configuration."""
    config = get_config()

    if show:
        import yaml
        console.print(Panel(yaml.dump(config.model_dump(mode="json")), title="Current Config"))

    if edit:
        import subprocess
        editor = "code"  # VS Code
        try:
            subprocess.run([editor, ".documentor.yaml"], check=True)
        except FileNotFoundError:
            console.print("[red]Editor not found. Set EDITOR env var or use --show.[/red]")


if __name__ == "__main__":
    app()
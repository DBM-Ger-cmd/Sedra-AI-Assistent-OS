"""CLI Commands.

Command-line interface for the module.
"""
import typer

app = typer.Typer(name="MODULE_NAME", help="MODULE_NAME CLI")

@app.command()
def hello(name: str = "World"):
    """Say hello."""
    typer.echo(f"Hello, {name}!")

@app.command()
def version():
    """Show version."""
    typer.echo("MODULE_NAME v0.1.0")

if __name__ == "__main__":
    app()
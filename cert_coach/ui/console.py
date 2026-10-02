"""Terminal console and themed styling utilities."""

from __future__ import annotations

import sys
from rich.console import Console
from rich.panel import Panel
from rich.theme import Theme

THEME = Theme(
    {
        "brand": "bold #FF9900",
        "aws_orange": "bold #FF9900",
        "aws_blue": "bold #0073BB",
        "aws_navy": "#232F3E",
        "accent": "bold #0073BB",
        "gold": "bold bright_yellow",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "dimmed": "dim white",
        "highlight": "bold #FF9900",
        "harness": "bold #0073BB",
        "exam": "bold #FF9900",
    }
)

console = Console(theme=THEME)
error_console = Console(theme=THEME, stderr=True)


def is_interactive() -> bool:
    """Check if stdout is connected to an interactive terminal."""
    return sys.stdout.isatty()


def print_step(title: str, detail: str = "") -> None:
    """Print a styled workflow step."""
    if detail:
        console.print(f"  [success]✓[/success] [bold white]{title}[/bold white] [dimmed]({detail})[/dimmed]")
    else:
        console.print(f"  [success]✓[/success] [bold white]{title}[/bold white]")


def print_info(message: str) -> None:
    """Print an informational bullet."""
    console.print(f"  [brand]ℹ[/brand] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"  [warning]⚠[/warning] [warning]{message}[/warning]")


def print_error(message: str) -> None:
    """Print an error message."""
    error_console.print(f"  [error]✗[/error] [error]{message}[/error]")

"""Animated AWS Professor Owl mascot and welcome banners with wing movement."""

from __future__ import annotations

import os
import time
from typing import Any, Callable
from rich.align import Align
from rich.box import ROUNDED
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from cert_coach.ui.console import console, is_interactive

WING_STYLES: dict[str, list[str]] = {
    # 0: Resting at sides
    "rest": [
        "[bold white] ╭██[/][#3E2723]██[bold #FF9900]a[white]w[/]s[/]██[/][bold white]██╮ [/]",
        "[bold white] │██[/][#3E2723]██[bold #FF9900] ─── [/]██[/][bold white]██│ [/]",
        "[bold white] │██[/][#3E2723]██[bold #FF9900]  ╰╯ [/]██[/][bold white]██│ [/]",
        "[bold white] ╰──[/][#3E2723]███████[/][bold white]──╯ [/]",
    ],
    # 1: Flapped UP
    "up": [
        "[bold white] ╱██[/][#3E2723]██[bold #FF9900]a[white]w[/]s[/]██[/][bold white]██╲ [/]",
        "[bold white]╱ ██[/][#3E2723]██[bold #FF9900] ─── [/]██[/][bold white]██ ╲[/]",
        "[bold white]  ██[/][#3E2723]██[bold #FF9900]  ╰╯ [/]██[/][bold white]██  [/]",
        "[bold white] ╰──[/][#3E2723]███████[/][bold white]──╯ [/]",
    ],
    # 2: Spread OUT
    "out": [
        "[bold white] ┌██[/][#3E2723]██[bold #FF9900]a[white]w[/]s[/]██[/][bold white]██┐ [/]",
        "[bold white]< ██[/][#3E2723]██[bold #FF9900] ─── [/]██[/][bold white]██ >[/]",
        "[bold white]  ██[/][#3E2723]██[bold #FF9900]  ╰╯ [/]██[/][bold white]██  [/]",
        "[bold white] ╰──[/][#3E2723]███████[/][bold white]──╯ [/]",
    ],
    # 3: Waving right wing
    "wave": [
        "[bold white] ╭██[/][#3E2723]██[bold #FF9900]a[white]w[/]s[/]██[/][bold white]██╲ [/]",
        "[bold white] │██[/][#3E2723]██[bold #FF9900] ─── [/]██[/][bold white]██ ╲[/]",
        "[bold white] │██[/][#3E2723]██[bold #FF9900]  ╰╯ [/]██[/][bold white]██  [/]",
        "[bold white] ╰──[/][#3E2723]███████[/][bold white]──╯ [/]",
    ],
}

# Animation frames: (eyes, wing_style, status_text, subtitle, duration)
OWL_ANIMATION_FRAMES = [
    (" - ", "rest", "Waking up Professor Owl...", "Booting study engine", 0.22),
    (" ◕ ", "up", "Stretching & flapping wings...", "Connecting to shared memory", 0.22),
    (" ◕ ", "out", "Wings spread! Inspecting blueprint...", "Syncing multi-agent harnesses", 0.22),
    (" ◕ ", "up", "Fluttering wings...", "Readying exam catalog", 0.22),
    (" ◕ ", "wave", "Professor Owl waves hello!", "Multi-agent engine online", 0.28),
    (" ◕ ", "rest", "Ready to architect your certification journey!", "Select options below to begin", 0.1),
]


def render_owl_panel(
    eyes: str = " ◕ ",
    wing: str = "rest",
    status: str = "Ready to architect your certification journey!",
    subtitle: str = "Professor Owl Online",
) -> Panel:
    """Build the Professor Owl mascot panel with AWS theme and dynamic wings."""
    wings = WING_STYLES.get(wing, WING_STYLES["rest"])
    owl_lines = [
        "[#8D6E63]    ▄███████▄    [/]",
        "[#8D6E63]  ▄█[/][bold white]┌───┐ ┌───┐[/][#8D6E63]█▄  [/]",
        f"[#8D6E63]  ██[/][bold white]│[bold black]{eyes}[/]│[bold #FF9900]▲[/]│[bold black]{eyes}[/]│[/][#8D6E63]██  [/]",
        "[#8D6E63]  ██[/][bold white]└───┘ └───┘[/][#8D6E63]██  [/]",
        wings[0],
        wings[1],
        wings[2],
        wings[3],
        "[bold #FF9900]     ╨╨   ╨╨     [/]",
    ]

    text_lines = [
        "",
        "[bold #FF9900]⚡ CERT-COACH CLI[/] [dim white]v0.3.0[/]",
        "[bold white]AWS Certification Study Engine[/]",
        "[dim #0073BB]SAA-C03 • CLF-C02 • AIF-C01[/]",
        "",
        "[bold #232F3E on #FF9900] AWS [/] [dim white]Multi-Agent Coexistence & Shared Memory[/]",
        "[dim]Kiro • Claude Code • Agy CLI • Local SQLite[/]",
        "",
        f"[dim italic]\"{status}\"[/]",
    ]

    grid = Table.grid(padding=(0, 2))
    grid.add_column(justify="center")
    grid.add_column(justify="left", vertical="middle")
    grid.add_row("\n".join(owl_lines), "\n".join(text_lines))

    return Panel(
        grid,
        box=ROUNDED,
        border_style="#FF9900",
        title="[bold white] AWS Certification Study Coach [/bold white]",
        subtitle=f"[bold #FF9900]●[/] [dim white]{subtitle}[/dim white]",
        padding=(0, 2),
    )


def play_mascot_animation(force: bool = False, loops: int = 2) -> None:
    """Play smooth mascot animation with wing movement across multiple loops.

    Uses in-place live updating so the animation is clearly visible and
    leaves the final panel cleanly on screen without flashing.
    """
    if not force and (
        not is_interactive()
        or os.environ.get("CI")
        or os.environ.get("CERT_COACH_NO_ANIMATION")
    ):
        render_static_welcome()
        return

    try:
        with Live(console=console, refresh_per_second=15, transient=False) as live:
            for _ in range(loops):
                for eyes, wing, status, subtitle, duration in OWL_ANIMATION_FRAMES:
                    live.update(
                        render_owl_panel(
                            eyes=eyes,
                            wing=wing,
                            status=status,
                            subtitle=subtitle,
                        )
                    )
                    time.sleep(duration)
        console.print()
    except (KeyboardInterrupt, Exception):
        render_static_welcome()


def run_scaffolding_with_mascot(
    tasks: list[tuple[str, Callable[[], Any]]],
    total_steps: int | None = None,
    interactive: bool = True,
) -> None:
    """Execute scaffolding steps while Professor Owl actively flaps his wings in a live loop."""
    if not interactive or os.environ.get("CI") or os.environ.get("CERT_COACH_NO_ANIMATION"):
        for step_label, task_fn in tasks:
            task_fn()
            console.print(f"  [green]✓[/green] [bold white]{step_label}[/bold white]")
        return

    n_steps = total_steps or len(tasks)
    wing_sequence = ["up", "out", "wave", "up", "rest"]

    try:
        with Live(console=console, refresh_per_second=15, transient=False) as live:
            for idx, (step_label, task_fn) in enumerate(tasks, 1):
                wing = wing_sequence[(idx - 1) % len(wing_sequence)]
                live.update(
                    render_owl_panel(
                        eyes=" ◕ ",
                        wing=wing,
                        status=f"Step {idx}/{n_steps}: {step_label}",
                        subtitle="Scaffolding Workspace in Progress...",
                    )
                )
                task_fn()
                time.sleep(0.35)

            # Final frame: rested with natural eyes
            live.update(
                render_owl_panel(
                    eyes=" ◕ ",
                    wing="rest",
                    status="All study components ready! Workspace initialized.",
                    subtitle="Configuration Complete",
                )
            )
            time.sleep(0.25)
        console.print()
    except (KeyboardInterrupt, Exception):
        # Fallback if interrupted
        for step_label, task_fn in tasks:
            try:
                task_fn()
            except Exception:
                pass


def render_static_welcome() -> None:
    """Print the static Professor Owl banner."""
    panel = render_owl_panel(
        eyes=" ◕ ",
        wing="rest",
        status="Ready to architect your certification journey!",
        subtitle="Select options below to begin",
    )
    console.print(panel)
    console.print()

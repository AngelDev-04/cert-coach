"""Interactive CLI prompts for wizard setup."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cert_coach.core.config import DEFAULT_SHARED_DB
from cert_coach.core.models import ExamType, HarnessType
from cert_coach.exams.registry import ExamRegistry
from cert_coach.ui.console import console


def prompt_workspace_path(default: str = ".") -> Path:
    """Prompt user for target workspace directory."""
    raw_cwd = Path.cwd().resolve()
    # If the user is currently inside the cert_coach package directory, default to the repository root
    cwd = raw_cwd.parent if raw_cwd.name == "cert_coach" else raw_cwd

    prompt_msg = (
        f"Where would you like to initialize your study coach?\n"
        f"  (Press Enter to initialize in [{cwd.name}/], or paste/type folder path):"
    )

    def validate_path(text: str) -> bool | str:
        cleaned = text.strip()
        if "@" in cleaned and ":" in cleaned and ("$" in cleaned or "#" in cleaned):
            return "That looks like a terminal prompt. Press Enter for repository root, or type a clean folder path."
        return True

    try:
        import questionary

        response = questionary.text(
            prompt_msg,
            default="",
            validate=validate_path,
        ).ask()
        if response is None:
            raise KeyboardInterrupt
        cleaned = response.strip()
        if not cleaned or cleaned == ".":
            return cwd
        return Path(cleaned).expanduser().resolve()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        from rich.prompt import Prompt

        val = Prompt.ask(
            f"Workspace directory (Press Enter for [{cwd.name}/], or paste folder path)",
            default="",
        )
        cleaned = val.strip() if val else ""
        if not cleaned or cleaned == ".":
            return cwd
        return Path(cleaned).expanduser().resolve()


def prompt_harness_selection(defaults: list[str] | None = None) -> list[str]:
    """Prompt user to select one or more AI agent harnesses (Multi-select)."""
    defaults = defaults or ["kiro"]
    choices = [
        {"name": "Kiro / Kiro-CLI (Power: POWER.md + skills + steering)", "value": "kiro", "checked": "kiro" in defaults},
        {"name": "Claude Code (Slash commands: .claude/commands/ + CLAUDE.md)", "value": "claude", "checked": "claude" in defaults},
        {"name": "Agy CLI / Antigravity (Skills + Rules: .gemini/ & .agents/)", "value": "agy", "checked": "agy" in defaults},
        {"name": "OpenAI Codex CLI (AGENTS.md + .codex/config.toml + .agents/skills/)", "value": "codex", "checked": "codex" in defaults},
    ]

    try:
        import questionary
        from questionary import Choice

        q_choices = [
            Choice(c["name"], value=c["value"], checked=c["checked"])
            for c in choices
        ]
        result = questionary.checkbox(
            "Select your AI Agent Harness(es) (multi-agent coexistence enabled):",
            choices=q_choices,
            validate=lambda a: True if len(a) > 0 else "Please select at least one harness.",
        ).ask()
        if result is None:
            raise KeyboardInterrupt
        return list(result)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        console.print("[dimmed]Defaulting to Kiro harness (interactive UI fallback)[/dimmed]")
        return defaults


def prompt_exam_selection(default: str = "saa-c03") -> str:
    """Prompt user to select a target certification exam."""
    exams = ExamRegistry.list_exams()
    choices = []
    for exam in exams:
        label = f"{exam.code} - {exam.name} [{exam.status.upper()}]"
        choices.append({"name": label, "value": exam.code.lower()})

    try:
        import questionary
        from questionary import Choice

        q_choices = [
            Choice(c["name"], value=c["value"])
            for c in choices
        ]
        result = questionary.select(
            "Select your target AWS Certification Exam:",
            choices=q_choices,
            default=next((c for c in q_choices if c.value == default), q_choices[0]),
        ).ask()
        if result is None:
            raise KeyboardInterrupt
        return str(result)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return default


def prompt_database_location(default_shared: bool = True) -> str:
    """Prompt user to select centralized shared database or project-local."""
    choices = [
        {
            "name": f"Shared across all projects & harnesses ({DEFAULT_SHARED_DB}) [Recommended]",
            "value": str(DEFAULT_SHARED_DB),
        },
        {
            "name": "Project-local database (.cert-coach/study-memory.sqlite3)",
            "value": ".cert-coach/study-memory.sqlite3",
        },
    ]

    try:
        import questionary
        from questionary import Choice

        q_choices = [Choice(c["name"], value=c["value"]) for c in choices]
        result = questionary.select(
            "Configure Local Study Database location:",
            choices=q_choices,
            default=q_choices[0] if default_shared else q_choices[1],
        ).ask()
        if result is None:
            raise KeyboardInterrupt
        return str(result)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return str(DEFAULT_SHARED_DB)

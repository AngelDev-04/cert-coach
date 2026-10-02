"""Command-line interface for cert-coach."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

from rich.panel import Panel
from rich.table import Table

from cert_coach.adapters import get_adapter, list_adapters
from cert_coach.core.config import (
    CONFIG_FILENAME,
    DEFAULT_SHARED_DB,
    TEMPLATES_DIR,
    WORKSPACE_DIRNAME,
    WorkspaceManager,
    create_private_file,
    default_workspace_root,
    find_existing_workspace,
    write_workspace_pointer,
)
from cert_coach.core.models import ExamType, HarnessType, WorkspaceConfig
from cert_coach.exams.registry import ExamRegistry
from cert_coach.mcp.launcher import run_mcp_server
from cert_coach.ui.console import (
    console,
    error_console,
    is_interactive,
    print_error,
    print_info,
    print_step,
    print_warning,
)
from cert_coach.ui.mascot import (
    play_mascot_animation,
    render_static_welcome,
    run_scaffolding_with_mascot,
)
from cert_coach.ui.prompts import (
    prompt_database_location,
    prompt_exam_selection,
    prompt_harness_selection,
)


# Command used to launch each harness from inside the workspace folder.
HARNESS_LAUNCH_COMMANDS: dict[str, tuple[str, str]] = {
    "claude": ("Claude Code", "claude"),
    "kiro": ("Kiro CLI", "kiro-cli"),
    "agy": ("Antigravity (agy)", "agy"),
    "codex": ("OpenAI Codex CLI", "codex"),
}


def resolve_workspace_root(chosen: Path, default_root: Path | None = None) -> Path:
    """Map a user-chosen folder to the actual workspace root.

    - An existing workspace (has .cert-coach.json) is reused as-is.
    - The default root (~/cert-coach or $CERT_COACH_HOME) is used as-is.
    - A folder already named 'cert-coach' (that is not a source checkout) is used as-is.
    - Otherwise a 'cert-coach/' subfolder is created inside the chosen folder.
    """
    chosen = chosen.expanduser().resolve()
    default_root = (default_root or default_workspace_root()).expanduser().resolve()
    if (chosen / CONFIG_FILENAME).is_file():
        return chosen
    if chosen == default_root and not (chosen / "cert_coach" / "cli.py").is_file():
        return chosen
    if chosen.name == WORKSPACE_DIRNAME and not (chosen / "cert_coach" / "cli.py").is_file():
        return chosen
    return chosen / WORKSPACE_DIRNAME


def _is_package_source(path: Path) -> bool:
    """Return True if path is (inside) the installed/checked-out cert_coach package."""
    package_dir = TEMPLATES_DIR.parent.resolve()
    resolved = path.resolve()
    if resolved == package_dir or package_dir in resolved.parents:
        return True
    return resolved.name == "cert_coach" or (
        (resolved / "adapters").is_dir() and (resolved / "cli.py").is_file()
    )


def _locate_workspace(explicit_dir: str | None) -> tuple[Path, WorkspaceManager]:
    """Find an existing workspace: --dir, else cwd, else the registered/default workspace."""
    if explicit_dir:
        raw_root = Path(explicit_dir).expanduser().resolve()
        return raw_root, WorkspaceManager(raw_root)
    raw_root = Path.cwd().resolve()
    manager = WorkspaceManager(raw_root)
    if not manager.is_initialized():
        existing = find_existing_workspace()
        if existing is not None:
            return existing, WorkspaceManager(existing)
    return raw_root, manager


def _print_init_summary(
    workspace_root: Path,
    exam_label: str,
    harnesses: list[str],
    db_path: Path,
    instructions: list[str],
) -> None:
    """Print the post-init summary with copy-pasteable launch commands."""
    quoted_root = shlex.quote(str(workspace_root))

    details = [
        f"[bold white]Target Exam:[/bold white] [bold green]{exam_label}[/bold green]",
        f"[bold white]Harnesses Configured:[/bold white] [bold blue]{', '.join(harnesses)}[/bold blue]",
        f"[bold white]Shared Database:[/bold white] [dim]{db_path}[/dim]",
    ]
    console.print()
    console.print(
        Panel(
            "\n".join(details),
            title="[bold green]✓ Study Coach Successfully Initialized[/bold green]",
            border_style="green",
        )
    )

    if instructions:
        console.print()
        console.print("[bold cyan]Agent details:[/bold cyan]")
        for instr in instructions:
            console.print(instr, markup=False, highlight=False, soft_wrap=True)
            console.print()

    # Printed outside any panel with soft_wrap so paths/commands are never
    # broken by borders or line wrapping and can be copy-pasted verbatim.
    console.print()
    console.print("[bold green]Your study workspace is ready at:[/bold green]")
    console.print(f"  [bold]{workspace_root}[/bold]", soft_wrap=True, highlight=False)
    console.print()
    console.print("[bold yellow]Start your agent FROM that folder so it picks up the coach instructions and MCP config:[/bold yellow]")
    for harness in harnesses:
        label, command = HARNESS_LAUNCH_COMMANDS.get(harness, (harness, harness))
        console.print(f"  [dim]# {label}[/dim]")
        console.print(f"  cd {quoted_root} && {command}", markup=False, soft_wrap=True, highlight=False)
    console.print()
    console.print(
        "[dim]Launching the agent from any other folder will not load the study coach. "
        "Re-run 'cert-coach init' any time; it reuses this workspace.[/dim]"
    )
    console.print()


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a study coach workspace with interactive wizard or flags."""
    # Play character animation if interactive and not disabled
    if not args.no_animation and not args.non_interactive:
        play_mascot_animation()
    else:
        render_static_welcome()

    # 1. Resolve the workspace root. Default is a fixed, cwd-independent location
    #    (~/cert-coach or $CERT_COACH_HOME) so workspaces never get scattered.
    #    Idempotent: there is one workspace per user. If it already exists, init
    #    updates it in place instead of scaffolding a second copy elsewhere.
    default_root = default_workspace_root()
    existing_root = find_existing_workspace()
    if args.dir:
        workspace_root = resolve_workspace_root(Path(args.dir).expanduser().resolve(), default_root)
    elif existing_root is not None:
        workspace_root = existing_root
    else:
        workspace_root = resolve_workspace_root(default_root, default_root)

    if existing_root is not None and workspace_root != existing_root:
        if not args.relocate:
            print_error(
                f"A study workspace already exists at {existing_root}.\n"
                f"  Run 'cert-coach init' without --dir to update it in place, or add\n"
                f"  --relocate to move it to {workspace_root}."
            )
            return 1
        if workspace_root.exists() and any(workspace_root.iterdir()):
            print_error(f"Cannot relocate: {workspace_root} already exists and is not empty.")
            return 1
        if _is_package_source(workspace_root):
            print_error(f"Cannot relocate into the cert_coach source package ({workspace_root}).")
            return 1
        relocate_from: Path | None = existing_root
    else:
        relocate_from = None

    # Prevent inadvertent poisoning of package source directory
    if _is_package_source(workspace_root):
        print_error(
            f"Cannot initialize inside the cert_coach source package ({workspace_root}).\n"
            f"  Please choose another target folder (default: {default_root})."
        )
        return 1

    # Nothing is created, moved or written on disk until every prompt is answered,
    # so cancelling the wizard (Ctrl+C) leaves no trace.
    source_manager = WorkspaceManager(relocate_from or workspace_root)
    previous = source_manager.load_config() if source_manager.is_initialized() else None
    if relocate_from is not None:
        print_info(f"Will move study workspace {relocate_from} -> {workspace_root}")
    elif previous is not None:
        print_info(f"Updating existing study workspace in place: {workspace_root}")
    else:
        print_info(f"Study workspace will be created at {workspace_root} (use --dir to choose another folder)")

    # 2. Resolve harnesses
    if args.harness:
        harness_names = [h.strip().lower() for h in args.harness.split(",") if h.strip()]
    elif not args.non_interactive and is_interactive():
        harness_names = prompt_harness_selection(list(previous.harnesses) if previous and previous.harnesses else ["kiro"])
    elif previous is not None and previous.harnesses:
        harness_names = list(previous.harnesses)
    else:
        harness_names = ["kiro"]
    # Re-runs add harnesses; they never drop ones configured earlier.
    if previous is not None:
        harness_names = list(dict.fromkeys([*previous.harnesses, *harness_names]))

    # Validate harnesses
    selected_harnesses: list[HarnessType] = []
    for name in harness_names:
        try:
            selected_harnesses.append(HarnessType.from_string(name))
        except ValueError as e:
            print_error(str(e))
            return 1

    # 3. Resolve exam
    if args.exam:
        exam_key = args.exam.strip().lower()
    elif not args.non_interactive and is_interactive():
        exam_key = prompt_exam_selection(previous.exam if previous else "saa-c03")
    elif previous is not None:
        exam_key = previous.exam
    else:
        exam_key = "saa-c03"

    try:
        exam_meta = ExamRegistry.get_metadata(exam_key)
    except ValueError as e:
        print_error(str(e))
        return 1

    # 4. Resolve DB path
    if args.db:
        db_path = Path(args.db).expanduser().resolve()
    elif previous is not None and previous.database_path:
        db_path = Path(previous.database_path).expanduser().resolve()
    elif not args.non_interactive and is_interactive():
        chosen_db = prompt_database_location(default_shared=True)
        db_path = Path(chosen_db).expanduser()
        if not db_path.is_absolute():
            db_path = (workspace_root / db_path).resolve()
    else:
        db_path = DEFAULT_SHARED_DB.resolve()

    # All answers collected: now touch the disk.
    if relocate_from is not None:
        workspace_root.parent.mkdir(parents=True, exist_ok=True)
        if workspace_root.exists():
            workspace_root.rmdir()
        shutil.move(str(relocate_from), str(workspace_root))
        print_info(f"Moved study workspace {relocate_from} -> {workspace_root}")
    workspace_root.mkdir(parents=True, exist_ok=True)
    manager = WorkspaceManager(workspace_root)
    db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    instructions: list[str] = []

    def task_docs() -> None:
        docs_dir = workspace_root / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        catalog_data = ExamRegistry.get_catalog(exam_key)
        catalog_file = docs_dir / f"{exam_meta.code.lower()}-concept-catalog.json"
        catalog_file.write_text(json.dumps(catalog_data, indent=2) + "\n", encoding="utf-8")
        blueprint_md = ExamRegistry.get_blueprint_markdown(exam_key)
        blueprint_file = docs_dir / f"{exam_meta.code.lower()}-exam-blueprint.md"
        blueprint_file.write_text(blueprint_md, encoding="utf-8")
        src_rubric = TEMPLATES_DIR / "docs" / "question-quality-rubric.md"
        dest_rubric = docs_dir / "question-quality-rubric.md"
        if src_rubric.is_file():
            shutil.copy2(src_rubric, dest_rubric)

    def task_mcp() -> None:
        mcp_src = TEMPLATES_DIR / "study-memory-mcp"
        mcp_dest = workspace_root / "study-memory-mcp"
        # Always refresh so upgrades ship the new server; learner data lives in the DB, not here.
        if mcp_src.is_dir():
            shutil.copytree(
                mcp_src, mcp_dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )

    def task_harnesses() -> None:
        for h_type in selected_harnesses:
            adapter = get_adapter(h_type)
            files = adapter.generate(workspace_root, exam_key, db_path)
            instructions.append(adapter.get_instructions(workspace_root))

    def task_config() -> None:
        config = WorkspaceConfig(
            exam=exam_key,
            harnesses=[h.value for h in selected_harnesses],
            database_path=str(db_path),
        )
        if previous is not None and previous.created_at:
            config.created_at = previous.created_at
        manager.save_config(config)
        write_workspace_pointer(workspace_root)

    def task_db() -> None:
        create_private_file(db_path)
        conn = sqlite3.connect(db_path, timeout=3)
        conn.close()

    harness_str = ", ".join(h.value for h in selected_harnesses)
    scaffold_tasks = [
        (f"Generating {exam_meta.code} blueprint & catalog in docs/", task_docs),
        ("Deploying study-memory MCP stdio server", task_mcp),
        (f"Configuring harnesses ({harness_str})", task_harnesses),
        ("Writing workspace manifest (.cert-coach.json)", task_config),
        (f"Connecting to shared SQLite database ({db_path.name})", task_db),
    ]

    is_anim = is_interactive() and not args.non_interactive and not args.no_animation
    run_scaffolding_with_mascot(scaffold_tasks, interactive=is_anim)

    _print_init_summary(
        workspace_root=workspace_root,
        exam_label=f"{exam_meta.name} ({exam_meta.code})",
        harnesses=[h.value for h in selected_harnesses],
        db_path=db_path,
        instructions=instructions,
    )
    return 0


def cmd_add_harness(args: argparse.Namespace) -> int:
    """Add a new agent harness to an existing workspace."""
    raw_root, manager = _locate_workspace(args.dir)

    if not manager.is_initialized():
        print_error(f"Directory '{raw_root}' is not a cert-coach workspace. Run 'cert-coach init' first.")
        return 1

    workspace_root = manager.root
    config = manager.load_config()
    db_path = config.resolve_db_path(workspace_root)

    try:
        h_type = HarnessType.from_string(args.harness)
    except ValueError as e:
        print_error(str(e))
        return 1

    adapter = get_adapter(h_type)
    files = adapter.generate(workspace_root, config.exam, db_path)
    manager.add_harness(h_type.value)

    print_step(f"Added harness: [bold blue]{adapter.display_name}[/bold blue]", f"{len(files)} files created")
    console.print()
    _, launch_cmd = HARNESS_LAUNCH_COMMANDS.get(h_type.value, (h_type.value, h_type.value))
    console.print("[bold yellow]Start the agent from the workspace folder:[/bold yellow]")
    console.print(f"  cd {shlex.quote(str(workspace_root))} && {launch_cmd}", markup=False, soft_wrap=True, highlight=False)
    console.print()
    console.print(adapter.get_instructions(workspace_root))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show workspace status, active harnesses, and learner database statistics."""
    raw_root, manager = _locate_workspace(args.dir)

    if not manager.is_initialized():
        print_error(f"'{raw_root}' is not an initialized cert-coach workspace.")
        return 1

    workspace_root = manager.root
    config = manager.load_config()
    exam_meta = ExamRegistry.get_metadata(config.exam)
    db_path = config.resolve_db_path(workspace_root)

    table = Table(title="Cert-Coach Workspace Status", box=None)
    table.add_column("Property", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Workspace Root", str(workspace_root))
    table.add_row("Target Exam", f"{exam_meta.name} ({exam_meta.code})")
    table.add_row("Configured Harnesses", ", ".join(config.harnesses))
    table.add_row("Shared SQLite DB", str(db_path))

    # Read DB stats if exists
    if db_path.is_file():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

            attempts_count = 0
            profiles_count = 0
            cards_count = 0

            if "objective_attempts" in tables:
                cursor.execute("SELECT COUNT(*) FROM objective_attempts")
                attempts_count = cursor.fetchone()[0]
            if "learner_profiles" in tables:
                cursor.execute("SELECT COUNT(*) FROM learner_profiles")
                profiles_count = cursor.fetchone()[0]
            if "flashcards" in tables:
                cursor.execute("SELECT COUNT(*) FROM flashcards")
                cards_count = cursor.fetchone()[0]

            conn.close()

            table.add_row("DB Status", f"[green]Connected[/green] ({db_path.stat().st_size:,} bytes)")
            table.add_row("Total Quiz Attempts", str(attempts_count))
            table.add_row("Learner Profiles", str(profiles_count))
            table.add_row("Flashcards Created", str(cards_count))
        except Exception as exc:
            table.add_row("DB Status", f"[yellow]Error reading database: {exc}[/yellow]")
    else:
        table.add_row("DB Status", "[yellow]Database file will be created on first study attempt[/yellow]")

    panel = Panel(table, border_style="cyan", title="[bold white] Workspace Overview [/bold white]")
    console.print(panel)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Run health diagnostics on Python, MCP server, DB, and harness configs."""
    console.print("[bold cyan]Running Cert-Coach Health Diagnostics...[/bold cyan]")
    console.print()

    all_passed = True

    # 1. Python version check
    py_ver = sys.version_info
    if py_ver >= (3, 10):
        print_step("Python Version", f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}")
    else:
        print_error(f"Python 3.10+ required. Current: {py_ver.major}.{py_ver.minor}")
        all_passed = False

    # 2. Workspace check
    raw_root, manager = _locate_workspace(args.dir)
    if manager.is_initialized():
        workspace_root = manager.root
        config = manager.load_config()
        print_step("Workspace Config", f"Valid .cert-coach.json (Exam: {config.exam})")

        # 3. Check DB access
        db_path = config.resolve_db_path(workspace_root)
        try:
            db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            create_private_file(db_path)
            conn = sqlite3.connect(db_path, timeout=2)
            conn.close()
            print_step("SQLite DB Access", f"Writable at {db_path}")
        except Exception as e:
            print_error(f"Failed to access DB at {db_path}: {e}")
            all_passed = False

        # 4. Check harnesses
        for h_str in config.harnesses:
            try:
                adapter = get_adapter(h_str)
                if adapter.is_configured(workspace_root):
                    print_step(f"Harness Config ({adapter.display_name})", "All files present")
                else:
                    print_warning(f"Harness '{adapter.display_name}' partially configured")
            except Exception as e:
                print_error(f"Harness check failed for {h_str}: {e}")
                all_passed = False
    else:
        print_info(f"Directory '{raw_root}' is not initialized. Run 'cert-coach init' to configure.")

    # 5. Check MCP server executable
    check_root = manager.root if manager.is_initialized() else raw_root
    workspace_server_py = check_root / "study-memory-mcp" / "server.py"
    server_py = workspace_server_py if workspace_server_py.is_file() else (TEMPLATES_DIR / "study-memory-mcp" / "server.py")
    if server_py.is_file():
        print_step("MCP Server Script", f"Found at {server_py}")
    else:
        print_warning(f"MCP server script not found at {server_py}")

    console.print()
    if all_passed:
        console.print("[bold green]✓ All diagnostic checks passed![/bold green]")
        return 0
    else:
        console.print("[bold red]✗ Some checks failed. See above details.[/bold red]")
        return 1


def cmd_mcp(args: argparse.Namespace) -> int:
    """Launch the stdio MCP server directly."""
    db_path = args.db
    if not db_path:
        raw_root = Path(args.dir).resolve() if args.dir else Path.cwd().resolve()
        manager = WorkspaceManager(raw_root)
        if manager.is_initialized():
            workspace_root = manager.root
            config = manager.load_config()
            db_path = str(config.resolve_db_path(workspace_root))
        else:
            db_path = str(DEFAULT_SHARED_DB)

    run_mcp_server(db_path=db_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="cert-coach",
        description="Adaptive Multi-Agent Certification Study Coach CLI",
    )
    parser.add_argument("--version", action="version", version="cert-coach 0.3.0")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize a study coach workspace")
    init_parser.add_argument("--dir", "-d", help="Target directory for the workspace")
    init_parser.add_argument("--harness", "-H", help="Harnesses to configure (comma-separated: kiro,claude,agy,codex)")
    init_parser.add_argument("--exam", "-e", help="Target exam (saa-c03, clf-c02, aif-c01)")
    init_parser.add_argument("--db", help="Path to SQLite database")
    init_parser.add_argument("--non-interactive", "-y", action="store_true", help="Skip interactive prompts")
    init_parser.add_argument("--no-animation", action="store_true", help="Disable character boot animation")
    init_parser.add_argument(
        "--relocate", action="store_true", help="Move the existing workspace to --dir instead of refusing"
    )

    # add-harness
    add_parser = subparsers.add_parser("add-harness", help="Add an agent harness to the current workspace")
    add_parser.add_argument("harness", help="Harness name (kiro, claude, agy, codex)")
    add_parser.add_argument("--dir", "-d", help="Workspace directory")

    # status / info
    status_parser = subparsers.add_parser("status", help="Show workspace status and database stats")
    status_parser.add_argument("--dir", "-d", help="Workspace directory")

    info_parser = subparsers.add_parser("info", help="Alias for status")
    info_parser.add_argument("--dir", "-d", help="Workspace directory")

    # doctor
    doc_parser = subparsers.add_parser("doctor", help="Run diagnostic health checks")
    doc_parser.add_argument("--dir", "-d", help="Workspace directory")

    # mcp
    mcp_parser = subparsers.add_parser("mcp", help="Launch stdio MCP server")
    mcp_parser.add_argument("--db", help="Override database path")
    mcp_parser.add_argument("--dir", "-d", help="Workspace directory")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entrypoint for the CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if not args.command:
            # Default to interactive init if run without arguments in terminal
            if is_interactive():
                args.command = "init"
                args.dir = None
                args.harness = None
                args.exam = None
                args.db = None
                args.non_interactive = False
                args.no_animation = False
                return cmd_init(args)
            parser.print_help()
            return 0

        if args.command == "init":
            return cmd_init(args)
        if args.command == "add-harness":
            return cmd_add_harness(args)
        if args.command in ("status", "info"):
            return cmd_status(args)
        if args.command == "doctor":
            return cmd_doctor(args)
        if args.command == "mcp":
            return cmd_mcp(args)

        parser.print_help()
        return 0
    except KeyboardInterrupt:
        console.print()
        console.print("  [dim red]Operation cancelled by user.[/dim red]")
        return 130


if __name__ == "__main__":
    sys.exit(main())

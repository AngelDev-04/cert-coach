"""Unit and integration tests for the cert-coach CLI."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from cert_coach.cli import build_parser, main
from cert_coach.core.config import WorkspaceManager
from cert_coach.core.models import WorkspaceConfig


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.db_patcher = patch("cert_coach.cli.DEFAULT_SHARED_DB", self.workspace / "shared.db")
        self.db_patcher.start()
        # Never let a test fall back to the real ~/cert-coach
        self.env_patcher = patch.dict(
            os.environ,
            {
                "CERT_COACH_HOME": str(self.workspace / "default-home"),
                "CERT_COACH_STATE_DIR": str(self.workspace / "state"),
            },
        )
        self.env_patcher.start()

    def tearDown(self) -> None:
        self.env_patcher.stop()
        self.db_patcher.stop()
        self.temp_dir.cleanup()

    def test_parser_recognizes_commands(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["init", "--dir", "/tmp", "--harness", "kiro", "--non-interactive"])
        self.assertEqual(args.command, "init")
        self.assertEqual(args.dir, "/tmp")
        self.assertEqual(args.harness, "kiro")
        self.assertTrue(args.non_interactive)

    @unittest.skipIf(os.name == "nt", "POSIX permissions only")
    def test_init_creates_private_database_and_state_dir(self) -> None:
        db_path = self.workspace / "private-db" / "study.sqlite3"
        exit_code = main([
            "init",
            "--dir", str(self.workspace),
            "--harness", "claude",
            "--db", str(db_path),
            "--non-interactive",
            "--no-animation",
        ])
        self.assertEqual(exit_code, 0)
        self.assertEqual(stat.S_IMODE(db_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(db_path.parent.stat().st_mode) & 0o077, 0)
        self.assertEqual(stat.S_IMODE((self.workspace / "state").stat().st_mode) & 0o077, 0)

    def test_init_command_creates_workspace(self) -> None:
        exit_code = main([
            "init",
            "--dir", str(self.workspace),
            "--harness", "kiro,claude",
            "--exam", "saa-c03",
            "--db", str(self.workspace / "study.sqlite3"),
            "--non-interactive",
            "--no-animation",
        ])
        self.assertEqual(exit_code, 0)

        # Manager initialized from parent resolves to isolated cert-coach directory
        manager = WorkspaceManager(self.workspace)
        self.assertTrue(manager.is_initialized())
        self.assertEqual(manager.root, self.workspace / "cert-coach")

        config = manager.load_config()
        self.assertEqual(config.exam, "saa-c03")
        self.assertEqual(config.harnesses, ["kiro", "claude"])

        # Dependencies and configs must be isolated inside cert-coach/
        cert_coach_dir = self.workspace / "cert-coach"
        self.assertTrue((cert_coach_dir / "POWER.md").is_file())
        self.assertTrue((cert_coach_dir / "CLAUDE.md").is_file())
        self.assertTrue((cert_coach_dir / "docs" / "saa-c03-exam-blueprint.md").is_file())
        # Parent directory must NOT be polluted
        self.assertFalse((self.workspace / "POWER.md").is_file())
        self.assertFalse((self.workspace / "CLAUDE.md").is_file())

    def test_init_clf_c02_and_aif_c01_workspaces(self) -> None:
        clf_dir = self.workspace / "clf-workspace"
        exit_code = main([
            "init",
            "--dir", str(clf_dir),
            "--harness", "kiro",
            "--exam", "clf-c02",
            "--non-interactive",
            "--no-animation",
        ])
        self.assertEqual(exit_code, 0)
        docs_clf = clf_dir / "cert-coach" / "docs"
        self.assertTrue((docs_clf / "clf-c02-exam-blueprint.md").is_file())
        self.assertTrue((docs_clf / "clf-c02-concept-catalog.json").is_file())

        # Switching exams updates the same workspace instead of creating another one
        exit_code = main([
            "init",
            "--exam", "aif-c01",
            "--non-interactive",
            "--no-animation",
        ])
        self.assertEqual(exit_code, 0)
        self.assertTrue((docs_clf / "aif-c01-exam-blueprint.md").is_file())
        self.assertTrue((docs_clf / "aif-c01-concept-catalog.json").is_file())
        config = json.loads((clf_dir / "cert-coach" / ".cert-coach.json").read_text())
        self.assertEqual(config["exam"], "aif-c01")

    def _snapshot(self, root: Path) -> dict[str, bytes]:
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
        }

    def _init(self, *extra: str) -> int:
        return main(["init", "--non-interactive", "--no-animation", *extra])

    def test_init_twice_is_idempotent(self) -> None:
        self.assertEqual(self._init("--harness", "kiro,claude,agy,codex"), 0)
        root = self.workspace / "default-home"
        first = self._snapshot(root)
        self.assertEqual(self._init("--harness", "kiro,claude,agy,codex"), 0)
        self.assertEqual(first, self._snapshot(root))
        self.assertEqual([p.name for p in self.workspace.iterdir() if p.name != "state"].count("default-home"), 1)

    def test_rerun_reuses_registered_workspace_from_any_cwd(self) -> None:
        custom = self.workspace / "custom"
        self.assertEqual(self._init("--dir", str(custom), "--harness", "claude"), 0)
        elsewhere = self.workspace / "elsewhere"
        elsewhere.mkdir()
        with patch("pathlib.Path.cwd", return_value=elsewhere):
            self.assertEqual(self._init(), 0)
        self.assertEqual(list(elsewhere.iterdir()), [])
        self.assertFalse((self.workspace / "default-home").exists())
        self.assertTrue((custom / "cert-coach" / ".cert-coach.json").is_file())

    def test_rerun_merges_harnesses_and_keeps_db_and_created_at(self) -> None:
        db = self.workspace / "my.sqlite3"
        self.assertEqual(self._init("--harness", "claude", "--db", str(db)), 0)
        manifest = self.workspace / "default-home" / ".cert-coach.json"
        before = json.loads(manifest.read_text())
        self.assertEqual(self._init("--harness", "codex"), 0)
        after = json.loads(manifest.read_text())
        self.assertEqual(after["harnesses"], ["claude", "codex"])
        self.assertEqual(after["database_path"], str(db.resolve()))
        self.assertEqual(after["created_at"], before["created_at"])

    def test_second_workspace_refused_without_relocate(self) -> None:
        self.assertEqual(self._init("--harness", "claude"), 0)
        other = self.workspace / "other"
        self.assertEqual(self._init("--dir", str(other)), 1)
        self.assertFalse(other.exists())

    def test_relocate_moves_workspace_and_rewrites_paths(self) -> None:
        self.assertEqual(self._init("--harness", "claude"), 0)
        other = self.workspace / "other"
        self.assertEqual(self._init("--dir", str(other), "--relocate"), 0)
        new_root = other / "cert-coach"
        self.assertFalse((self.workspace / "default-home").exists())
        mcp = json.loads((new_root / ".mcp.json").read_text())
        server = Path(mcp["mcpServers"]["study-memory"]["args"][0])
        self.assertEqual(server, (new_root / "study-memory-mcp" / "server.py").resolve())
        self.assertTrue(server.is_file())

    def test_cancelled_wizard_creates_nothing(self) -> None:
        root = self.workspace / "default-home"
        with patch("cert_coach.cli.is_interactive", return_value=True), patch(
            "cert_coach.cli.prompt_harness_selection", side_effect=KeyboardInterrupt
        ):
            self.assertNotEqual(main(["init", "--no-animation"]), 0)
        self.assertFalse(root.exists())
        self.assertFalse((self.workspace / "state").exists())

    def test_invalid_harness_creates_nothing(self) -> None:
        self.assertEqual(self._init("--harness", "nope"), 1)
        self.assertFalse((self.workspace / "default-home").exists())

    def test_cancelled_relocate_leaves_workspace_in_place(self) -> None:
        self.assertEqual(self._init("--harness", "claude"), 0)
        other = self.workspace / "other"
        with patch("cert_coach.cli.is_interactive", return_value=True), patch(
            "cert_coach.cli.prompt_harness_selection", side_effect=KeyboardInterrupt
        ):
            self.assertNotEqual(main(["init", "--no-animation", "--dir", str(other), "--relocate"]), 0)
        self.assertTrue((self.workspace / "default-home" / ".cert-coach.json").is_file())
        self.assertFalse(other.exists())

    def test_upgrade_refreshes_mcp_server(self) -> None:
        self.assertEqual(self._init("--harness", "claude"), 0)
        server = self.workspace / "default-home" / "study-memory-mcp" / "server.py"
        server.write_text("# stale\n")
        self.assertEqual(self._init(), 0)
        self.assertNotEqual(server.read_text(), "# stale\n")

    def test_add_harness_command(self) -> None:
        # First init with Kiro
        main([
            "init",
            "--dir", str(self.workspace),
            "--harness", "kiro",
            "--exam", "clf-c02",
            "--non-interactive",
            "--no-animation",
        ])

        # Then add Claude
        exit_code = main(["add-harness", "claude", "--dir", str(self.workspace)])
        self.assertEqual(exit_code, 0)

        manager = WorkspaceManager(self.workspace)
        config = manager.load_config()
        self.assertIn("claude", config.harnesses)
        cert_coach_dir = self.workspace / "cert-coach"
        self.assertTrue((cert_coach_dir / "CLAUDE.md").is_file())

    def test_status_and_doctor_commands(self) -> None:
        main([
            "init",
            "--dir", str(self.workspace),
            "--harness", "kiro,claude,agy,codex",
            "--exam", "aif-c01",
            "--non-interactive",
            "--no-animation",
        ])

        status_code = main(["status", "--dir", str(self.workspace)])
        self.assertEqual(status_code, 0)

        doc_code = main(["doctor", "--dir", str(self.workspace)])
        self.assertEqual(doc_code, 0)

    def test_init_with_codex_harness(self) -> None:
        exit_code = main([
            "init",
            "--dir", str(self.workspace),
            "--harness", "codex",
            "--exam", "saa-c03",
            "--non-interactive",
            "--no-animation",
        ])
        self.assertEqual(exit_code, 0)
        cert_coach_dir = self.workspace / "cert-coach"
        self.assertTrue((cert_coach_dir / "AGENTS.md").is_file())
        self.assertTrue((cert_coach_dir / "CODEX.md").is_file())
        self.assertTrue((cert_coach_dir / ".codex" / "config.toml").is_file())
        self.assertTrue((cert_coach_dir / ".agents" / "skills").is_dir())

    def test_init_displays_agent_init_path_message(self) -> None:
        from cert_coach.ui.console import console

        with console.capture() as capture:
            exit_code = main([
                "init",
                "--dir", str(self.workspace),
                "--harness", "kiro",
                "--exam", "saa-c03",
                "--non-interactive",
                "--no-animation",
            ])
            self.assertEqual(exit_code, 0)

        output = capture.get()
        expected_path = str(self.workspace / "cert-coach")
        self.assertIn("Your study workspace is ready at:", output)
        self.assertIn(expected_path, output)
        self.assertIn(f"cd {expected_path} && kiro-cli", output)
        # Only the selected harness gets a launch command
        self.assertNotIn("&& claude", output)
        self.assertNotIn("&& codex", output)

    def test_init_summary_lists_launch_command_per_harness(self) -> None:
        from cert_coach.ui.console import console

        with console.capture() as capture:
            exit_code = main([
                "init",
                "--dir", str(self.workspace),
                "--harness", "kiro,claude,agy,codex",
                "--non-interactive",
                "--no-animation",
            ])
        self.assertEqual(exit_code, 0)
        output = capture.get()
        root = self.workspace / "cert-coach"
        for cmd in ("claude", "kiro-cli", "agy", "codex"):
            self.assertIn(f"cd {root} && {cmd}", output)

    def _init_no_dir(self) -> int:
        return main(["init", "--harness", "claude", "--non-interactive", "--no-animation"])

    def test_init_without_dir_uses_default_home_root(self) -> None:
        fake_home = self.workspace / "home"
        fake_home.mkdir()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CERT_COACH_HOME", None)
            with patch("pathlib.Path.home", return_value=fake_home):
                exit_code = self._init_no_dir()
        self.assertEqual(exit_code, 0)
        root = fake_home / "cert-coach"
        self.assertTrue((root / ".cert-coach.json").is_file())
        self.assertTrue((root / "CLAUDE.md").is_file())
        self.assertFalse((root / "cert-coach").exists())
        # Home itself must stay clean
        self.assertFalse((fake_home / "CLAUDE.md").exists())
        self.assertFalse((fake_home / ".mcp.json").exists())

    def test_init_without_dir_ignores_cwd(self) -> None:
        cwd = self.workspace / "somewhere-random"
        cwd.mkdir()
        old_cwd = os.getcwd()
        os.chdir(cwd)
        try:
            exit_code = self._init_no_dir()
        finally:
            os.chdir(old_cwd)
        self.assertEqual(exit_code, 0)
        self.assertEqual(list(cwd.iterdir()), [])
        self.assertTrue((self.workspace / "default-home" / ".cert-coach.json").is_file())

    def test_cert_coach_home_env_override_is_not_nested(self) -> None:
        custom = self.workspace / "my-study-space"
        with patch.dict(os.environ, {"CERT_COACH_HOME": str(custom)}):
            exit_code = self._init_no_dir()
        self.assertEqual(exit_code, 0)
        self.assertTrue((custom / ".cert-coach.json").is_file())
        self.assertTrue((custom / "CLAUDE.md").is_file())
        self.assertFalse((custom / "cert-coach").exists())

    def test_explicit_dir_default_root_not_nested(self) -> None:
        default_root = self.workspace / "default-home"
        exit_code = main([
            "init", "--dir", str(default_root), "--harness", "kiro",
            "--non-interactive", "--no-animation",
        ])
        self.assertEqual(exit_code, 0)
        self.assertTrue((default_root / "POWER.md").is_file())
        self.assertFalse((default_root / "cert-coach").exists())

    def test_dir_flag_overrides_default_root(self) -> None:
        target = self.workspace / "explicit-parent"
        exit_code = main([
            "init", "--dir", str(target), "--harness", "kiro",
            "--non-interactive", "--no-animation",
        ])
        self.assertEqual(exit_code, 0)
        self.assertTrue((target / "cert-coach" / ".cert-coach.json").is_file())
        self.assertFalse((self.workspace / "default-home").exists())

    def test_reinit_reuses_existing_workspace(self) -> None:
        self.assertEqual(self._init_no_dir(), 0)
        root = self.workspace / "default-home"
        exit_code = main([
            "init", "--dir", str(root), "--harness", "codex",
            "--non-interactive", "--no-animation",
        ])
        self.assertEqual(exit_code, 0)
        self.assertTrue((root / "AGENTS.md").is_file())
        self.assertFalse((root / "cert-coach").exists())

    def test_init_refuses_package_source_dir(self) -> None:
        from cert_coach.core.config import TEMPLATES_DIR

        package_dir = TEMPLATES_DIR.parent
        exit_code = main([
            "init", "--dir", str(package_dir / "cert-coach"), "--harness", "kiro",
            "--non-interactive", "--no-animation",
        ])
        self.assertEqual(exit_code, 1)
        self.assertFalse((package_dir / "cert-coach").exists())

    def test_generated_mcp_configs_reference_existing_absolute_paths(self) -> None:
        exit_code = main([
            "init", "--dir", str(self.workspace), "--harness", "kiro,claude,agy,codex",
            "--non-interactive", "--no-animation",
        ])
        self.assertEqual(exit_code, 0)
        root = self.workspace / "cert-coach"
        found = 0
        for cfg in root.rglob("*"):
            if cfg.name not in ("mcp.json", ".mcp.json", "mcp_config.json"):
                continue
            data = json.loads(cfg.read_text(encoding="utf-8"))
            for server in data.get("mcpServers", {}).values():
                found += 1
                for arg in server.get("args", []):
                    if arg.endswith(".py"):
                        self.assertTrue(Path(arg).is_absolute(), f"{cfg}: {arg}")
                        self.assertTrue(Path(arg).is_file(), f"{cfg}: {arg}")
                        self.assertTrue(Path(arg).is_relative_to(root), f"{cfg}: {arg}")
                db = server.get("env", {}).get("STUDY_MEMORY_DB")
                if db:
                    self.assertTrue(Path(db).is_absolute(), f"{cfg}: {db}")
                    self.assertTrue(Path(db).is_file(), f"{cfg}: {db}")
        self.assertGreater(found, 0)


    def test_init_with_path_already_named_cert_coach(self) -> None:
        target = self.workspace / "cert-coach"
        exit_code = main([
            "init",
            "--dir", str(target),
            "--harness", "kiro",
            "--exam", "saa-c03",
            "--non-interactive",
            "--no-animation",
        ])
        self.assertEqual(exit_code, 0)
        # Should not create nested cert-coach/cert-coach
        self.assertTrue((target / "POWER.md").is_file())
        self.assertFalse((target / "cert-coach").exists())

    def test_invalid_harness_fails_cleanly(self) -> None:
        exit_code = main([
            "init",
            "--dir", str(self.workspace),
            "--harness", "nonexistent-agent",
            "--non-interactive",
            "--no-animation",
        ])
        self.assertEqual(exit_code, 1)

    def test_invalid_exam_fails_cleanly(self) -> None:
        exit_code = main([
            "init",
            "--dir", str(self.workspace),
            "--exam", "invalid-exam-xyz",
            "--non-interactive",
            "--no-animation",
        ])
        self.assertEqual(exit_code, 1)

    def test_keyboard_interrupt_exits_cleanly(self) -> None:
        from unittest.mock import patch
        with patch("cert_coach.cli.cmd_init", side_effect=KeyboardInterrupt):
            code = main(["init", "--dir", str(self.workspace)])
            self.assertEqual(code, 130)


if __name__ == "__main__":
    unittest.main()

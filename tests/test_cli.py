"""Unit and integration tests for the cert-coach CLI."""

from __future__ import annotations

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

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.temp_dir.cleanup()

    def test_parser_recognizes_commands(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["init", "--dir", "/tmp", "--harness", "kiro", "--non-interactive"])
        self.assertEqual(args.command, "init")
        self.assertEqual(args.dir, "/tmp")
        self.assertEqual(args.harness, "kiro")
        self.assertTrue(args.non_interactive)

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

        manager = WorkspaceManager(self.workspace)
        self.assertTrue(manager.is_initialized())
        config = manager.load_config()
        self.assertEqual(config.exam, "saa-c03")
        self.assertEqual(config.harnesses, ["kiro", "claude"])
        self.assertTrue((self.workspace / "POWER.md").is_file())
        self.assertTrue((self.workspace / "CLAUDE.md").is_file())
        self.assertTrue((self.workspace / "docs" / "saa-c03-exam-blueprint.md").is_file())

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
        self.assertTrue((self.workspace / "CLAUDE.md").is_file())

    def test_status_and_doctor_commands(self) -> None:
        main([
            "init",
            "--dir", str(self.workspace),
            "--harness", "kiro,claude,agy",
            "--exam", "aif-c01",
            "--non-interactive",
            "--no-animation",
        ])

        status_code = main(["status", "--dir", str(self.workspace)])
        self.assertEqual(status_code, 0)

        doc_code = main(["doctor", "--dir", str(self.workspace)])
        self.assertEqual(doc_code, 0)

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

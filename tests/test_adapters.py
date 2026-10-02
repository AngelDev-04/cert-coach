"""Unit tests for harness adapters and multi-agent coexistence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cert_coach.adapters import get_adapter, list_adapters
from cert_coach.adapters.agy import AgyCliAdapter
from cert_coach.adapters.claude import ClaudeCodeAdapter
from cert_coach.adapters.codex import CodexAdapter
from cert_coach.adapters.kiro import KiroAdapter
from cert_coach.core.models import HarnessType


class AdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.db_path = self.workspace / "test.sqlite3"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_list_and_get_adapters(self) -> None:
        adapters = list_adapters()
        self.assertEqual(len(adapters), 4)
        self.assertIsInstance(get_adapter("kiro"), KiroAdapter)
        self.assertIsInstance(get_adapter("claude"), ClaudeCodeAdapter)
        self.assertIsInstance(get_adapter("agy"), AgyCliAdapter)
        self.assertIsInstance(get_adapter("codex"), CodexAdapter)

    def test_kiro_adapter_generation(self) -> None:
        adapter = KiroAdapter()
        created = adapter.generate(self.workspace, "saa-c03", self.db_path)
        self.assertTrue((self.workspace / "POWER.md").is_file())
        self.assertTrue((self.workspace / "plugin.json").is_file())
        self.assertTrue((self.workspace / "mcp.json").is_file())
        self.assertTrue((self.workspace / "steering" / "steering.md").is_file())

        mcp_data = json.loads((self.workspace / "mcp.json").read_text(encoding="utf-8"))
        self.assertIn("study-memory", mcp_data["mcpServers"])
        self.assertTrue(adapter.is_configured(self.workspace))

    def test_claude_adapter_generation(self) -> None:
        adapter = ClaudeCodeAdapter()
        created = adapter.generate(self.workspace, "saa-c03", self.db_path)
        self.assertTrue((self.workspace / "CLAUDE.md").is_file())
        self.assertTrue((self.workspace / ".mcp.json").is_file())

        commands_dir = self.workspace / ".claude" / "commands"
        self.assertTrue(commands_dir.is_dir())
        expected_commands = {
            "plan.md",
            "diagnostic.md",
            "quiz.md",
            "mock.md",
            "flashcards.md",
            "progress.md",
            "teach.md",
            "scenario.md",
            "audit.md",
            "question-quality.md",
        }
        existing_commands = {p.name for p in commands_dir.glob("*.md")}
        self.assertTrue(expected_commands.issubset(existing_commands))
        self.assertTrue(adapter.is_configured(self.workspace))

    def test_agy_adapter_generation(self) -> None:
        adapter = AgyCliAdapter()
        created = adapter.generate(self.workspace, "saa-c03", self.db_path)
        self.assertTrue((self.workspace / "GEMINI.md").is_file())
        self.assertTrue((self.workspace / ".gemini" / "rules" / "question-presentation-contract.md").is_file())
        self.assertTrue((self.workspace / ".gemini" / "rules" / "privacy-contract.md").is_file())
        self.assertTrue((self.workspace / ".agents" / "rules" / "question-contract.md").is_file())
        self.assertTrue((self.workspace / ".gemini" / "skills").is_dir())
        self.assertTrue((self.workspace / ".agents" / "skills").is_dir())
        self.assertTrue((self.workspace / ".agents" / "skills.json").is_file())
        self.assertTrue((self.workspace / "mcp.json").is_file())
        self.assertTrue((self.workspace / "mcp_config.json").is_file())
        self.assertTrue(adapter.is_configured(self.workspace))

    def test_codex_adapter_generation(self) -> None:
        adapter = CodexAdapter()
        created = adapter.generate(self.workspace, "saa-c03", self.db_path)
        self.assertTrue((self.workspace / "AGENTS.md").is_file())
        self.assertTrue((self.workspace / "CODEX.md").is_file())
        self.assertTrue((self.workspace / ".codex" / "config.toml").is_file())
        self.assertTrue((self.workspace / ".agents" / "skills").is_dir())
        self.assertTrue((self.workspace / ".codex" / "skills").is_dir())

        toml_content = (self.workspace / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertIn("[mcp_servers.study-memory]", toml_content)
        self.assertIn("STUDY_MEMORY_DB", toml_content)
        self.assertTrue(adapter.is_configured(self.workspace))

    def test_multi_agent_coexistence(self) -> None:
        """Verify Kiro, Claude Code, Agy CLI, and OpenAI Codex can all coexist in the same directory."""
        for adapter in (KiroAdapter(), ClaudeCodeAdapter(), AgyCliAdapter(), CodexAdapter()):
            adapter.generate(self.workspace, "saa-c03", self.db_path)

        self.assertTrue(KiroAdapter().is_configured(self.workspace))
        self.assertTrue(ClaudeCodeAdapter().is_configured(self.workspace))
        self.assertTrue(AgyCliAdapter().is_configured(self.workspace))
        self.assertTrue(CodexAdapter().is_configured(self.workspace))


if __name__ == "__main__":
    unittest.main()

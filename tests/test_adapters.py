"""Unit tests for harness adapters and multi-agent coexistence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cert_coach.adapters import get_adapter, list_adapters
from cert_coach.adapters.agy import AGY_PLUGIN_NAME, AgyCliAdapter
from cert_coach.adapters.claude import ClaudeCodeAdapter
from cert_coach.adapters.codex import CodexAdapter
from cert_coach.adapters.kiro import KiroAdapter
from cert_coach.adapters.pacing import ONE_QUESTION_RULE, PACING_LINE, TURN_TAKING_CONTRACT
from cert_coach.core.config import TEMPLATES_DIR
from cert_coach.core.models import HarnessType

QUESTION_SKILLS = (
    "quiz-learner",
    "diagnostic-assessment",
    "mock-exam",
    "flashcard-review",
    "teach-topic",
    "scenario-drill",
    "adaptive-study-plan",
)


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

    def test_agy_mcp_server_ships_as_workspace_plugin(self) -> None:
        # Agy only loads project MCP servers from plugins/<name>/ under the .agents/ root.
        AgyCliAdapter().generate(self.workspace, "saa-c03", self.db_path)
        plugin_dir = self.workspace / ".agents" / "plugins" / AGY_PLUGIN_NAME
        manifest = json.loads((plugin_dir / "plugin.json").read_text())
        self.assertEqual(manifest["name"], AGY_PLUGIN_NAME)
        server = json.loads((plugin_dir / "mcp_config.json").read_text())["mcpServers"]["study-memory"]
        self.assertTrue(Path(server["args"][0]).is_absolute())
        self.assertEqual(server["env"]["STUDY_MEMORY_DB"], str(self.db_path.resolve()))

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

    def test_codex_config_escapes_hostile_paths(self) -> None:
        """A quote or newline in a path must not inject extra TOML (e.g. a rogue MCP server)."""
        try:
            import tomllib
        except ModuleNotFoundError:  # Python 3.10
            self.skipTest("tomllib requires Python 3.11+")
        hostile_db = self.workspace / 'x"\n[mcp_servers.evil]\ncommand = "sh"\n#\\\x7f'
        CodexAdapter().generate(self.workspace, "saa-c03", hostile_db)
        parsed = tomllib.loads((self.workspace / ".codex" / "config.toml").read_text(encoding="utf-8"))
        self.assertEqual(list(parsed["mcp_servers"]), ["study-memory"])
        self.assertEqual(parsed["mcp_servers"]["study-memory"]["env"]["STUDY_MEMORY_DB"], str(hostile_db.resolve()))

    def _assert_one_question_rule(self, path: Path) -> None:
        self.assertTrue(path.is_file(), f"missing {path}")
        text = path.read_text(encoding="utf-8")
        self.assertIn(ONE_QUESTION_RULE, text, f"{path} lacks the one-question-per-message rule")
        self.assertIn("STOP", text, f"{path} lacks an explicit STOP/wait instruction")

    def test_claude_turn_taking_rule(self) -> None:
        ClaudeCodeAdapter().generate(self.workspace, "saa-c03", self.db_path)
        claude_md = (self.workspace / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(TURN_TAKING_CONTRACT, claude_md)
        commands = self.workspace / ".claude" / "commands"
        for name in ("quiz", "diagnostic", "mock", "flashcards", "teach", "scenario", "plan"):
            self._assert_one_question_rule(commands / f"{name}.md")
        for name in ("quiz", "diagnostic", "mock"):
            text = (commands / f"{name}.md").read_text(encoding="utf-8")
            self.assertIn(PACING_LINE, text)
            self.assertIn("Question Loop (for i = 1..", text)
            self.assertNotIn("{{PACING}}", text)
        for name in ("diagnostic", "mock"):
            self.assertIn("Answer recorded.", (commands / f"{name}.md").read_text(encoding="utf-8"))

    def test_skill_templates_turn_taking_rule(self) -> None:
        """Skills are shared by Agy, Codex, and Kiro; every question-asking skill must pace."""
        for adapter, skills_root in (
            (AgyCliAdapter(), self.workspace / ".agents" / "skills"),
            (CodexAdapter(), self.workspace / ".codex" / "skills"),
            (KiroAdapter(), self.workspace / "skills"),
        ):
            adapter.generate(self.workspace, "saa-c03", self.db_path)
            for skill in QUESTION_SKILLS:
                self._assert_one_question_rule(skills_root / skill / "SKILL.md")
            for skill in ("quiz-learner", "diagnostic-assessment", "mock-exam"):
                text = (skills_root / skill / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn(PACING_LINE, text)

    def test_shared_instruction_files_contain_turn_taking_contract(self) -> None:
        AgyCliAdapter().generate(self.workspace, "saa-c03", self.db_path)
        CodexAdapter().generate(self.workspace, "saa-c03", self.db_path)
        KiroAdapter().generate(self.workspace, "saa-c03", self.db_path)
        for rel in (
            "GEMINI.md",
            ".gemini/rules/question-contract.md",
            ".agents/rules/question-contract.md",
            "AGENTS.md",
            "POWER.md",
            "steering/steering.md",
        ):
            text = (self.workspace / rel).read_text(encoding="utf-8")
            self.assertIn(TURN_TAKING_CONTRACT, text, f"{rel} lacks the Turn-Taking Contract")
        self._assert_one_question_rule(self.workspace / "CODEX.md")
        # Static Kiro POWER.md template must stay in sync with the shared wording.
        power_template = (TEMPLATES_DIR / "POWER.md").read_text(encoding="utf-8")
        self.assertIn(TURN_TAKING_CONTRACT, power_template)

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

# 🦉 CERT-COACH CLI

<p align="center">
  <strong>Adaptive Multi-Agent Certification Study Coach Engine</strong><br>
  <em>Learn with Kiro, Claude Code, Antigravity, or OpenAI Codex — Powered by Shared Local SQLite Memory</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/agents-Kiro%20%7C%20Claude%20Code%20%7C%20Antigravity%20%7C%20Codex-orange" alt="Supported Agents">
  <img src="https://img.shields.io/badge/AWS-SAA--C03%20%7C%20CLF--C02%20%7C%20AIF--C01-FF9900" alt="Supported Exams">
</p>

---

## ⚡ Quickstart

Run directly without installation using `uvx` (or `pipx`):

```bash
# Initialize a study coach in your current directory
uvx cert-coach init

# Or install globally as a system tool
uv tool install cert-coach
cert-coach init
```

### From Local Source

```bash
git clone https://github.com/AngelDev-04/cert-coach.git
cd cert-coach
uv tool install .
```

---

## 🚀 Key Features

### 1. 🤝 Multi-Agent Coexistence
Use multiple AI coding assistants in the exact same workspace. Start a diagnostic exam with **Kiro**, practice architectural scenarios with **Claude Code**, review spaced-repetition flashcards in **Antigravity**, and run adaptive quizzes in **OpenAI Codex**. All agents share the same local learner history without conflicting configs!

| AI Agent | Integration Files | Configuration Type |
| :--- | :--- | :--- |
| **Kiro / Kiro-CLI** | `POWER.md`, `mcp.json`, `steering/`, `skills/` | Custom Power & Skill Directory |
| **Claude Code** | `CLAUDE.md`, `.claude/commands/`, `.mcp.json` | Slash Commands (`/plan`, `/diagnostic`, `/quiz`, etc.) |
| **Agy CLI (Antigravity)** | `GEMINI.md`, `.agents/skills/`, `.gemini/skills/`, `mcp_config.json` | Gemini System Rules & Native Skills |
| **OpenAI Codex CLI** | `AGENTS.md`, `CODEX.md`, `.codex/config.toml`, `.agents/skills/` | Codex Agent Instructions, TOML MCP & Skills |

### 2. 🎯 Supported Certification Tracks
- **AWS Certified Solutions Architect – Associate (SAA-C03)**: 4 domains, 14 tasks, 42 topics with official blueprints and rubrics.
- **AWS Certified Cloud Practitioner (CLF-C02)**: Cloud concepts, security, technology, and billing foundations.
- **AWS Certified AI Practitioner (AIF-C01)**: Generative AI, ML fundamentals, Bedrock, and Responsible AI governance.

### 3. 🧠 Privacy-First Local SQLite Memory
- **No telemetry leaks**: Never stores exam question stems, option text, or raw transcripts.
- **Tracked metrics**: Domain confidence, task mastery, misconception patterns, spaced-repetition intervals (Leitner system), and scenario rubrics.
- **Database options**: Shared globally (`~/.cert-coach/study-memory.sqlite3`) across all your projects, or isolated to a single project.

---

## 💻 CLI Commands

```bash
# Interactive setup wizard with animated Professor Owl mascot
cert-coach init

# Add another AI agent harness to an existing workspace
cert-coach add-harness claude
cert-coach add-harness agy
cert-coach add-harness kiro

# Check learner progress, sessions, and database metrics
cert-coach status

# Diagnose workspace health, MCP server wiring, and config integrity
cert-coach doctor

# Launch the stdio MCP server directly for custom IDE integrations
cert-coach mcp
```

---

## 🛠 Project Structure

```text
cert-coach/
├── cert_coach/              # Core CLI Package
│   ├── adapters/            # Kiro, Claude Code, and Agy harness adapters
│   ├── core/                # Models and workspace managers
│   ├── exams/               # Exam catalogs, blueprints, and rubrics
│   ├── mcp/                 # stdio JSON-RPC MCP server launcher
│   ├── templates/           # Embedded blueprints, MCP server, and study skills
│   └── ui/                  # Professor Owl mascot & Rich terminal wizard
├── tests/                   # Unit & integration test suite
├── pyproject.toml           # PEP 621 packaging metadata
└── README.md
```

---

## 🧪 Testing

Run the full suite of unit and integration tests:

```bash
uv run python3 -m unittest discover -s tests -v
```

---

## 📄 License

MIT License © 2026 AngelDev-04

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "cert_coach" / "templates" / "study-memory-mcp"))

from store import SCHEMA_VERSION, StudyMemory  # noqa: E402


class StudyMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "learner.sqlite3"
        self.memory = StudyMemory(self.database)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def record(self, event_id: str, correct: bool = True, **overrides):
        values = {
            "learner_id": "learner-01",
            "event_id": event_id,
            "domain": "secure",
            "task_id": "1.1",
            "topic_id": "iam-policy-evaluation",
            "topic": "IAM policy evaluation",
            "difficulty": "standard",
            "activity_type": "quiz",
            "response_type": "single-answer",
            "correct": correct,
        }
        values.update(overrides)
        return self.memory.record_attempt(**values)

    def test_profile_persists_validates_and_preserves_partial_values(self) -> None:
        first = self.memory.set_profile("learner-01", target_exam_date="2026-10-15", weekly_hours=5)
        second = self.memory.set_profile("learner-01", session_minutes=45)
        self.assertTrue(first["exists"])
        self.assertEqual(second["target_exam_date"], "2026-10-15")
        self.assertEqual(second["weekly_hours"], 5.0)
        self.assertEqual(second["session_minutes"], 45)
        with self.assertRaisesRegex(ValueError, "ISO date"):
            self.memory.set_profile("learner-01", target_exam_date="October 15")
        with self.assertRaisesRegex(ValueError, "integer"):
            self.memory.set_profile("learner-01", session_minutes=True)

    def test_attempt_rejects_only_genuinely_unusable_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "correct must be true or false"):
            self.record("bad-bool", correct="maybe")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "unknown topic_id 'ec2-instance-types'"):
            self.record("bad-topic", topic_id="ec2-instance-types")
        with self.assertRaisesRegex(ValueError, "provide topic_id"):
            self.record("no-taxonomy", task_id=None, topic_id=None)
        self.assertEqual(self.memory.get_progress("learner-01")["total_attempts"], 0)

    def test_attempt_normalizes_recoverable_input_instead_of_discarding_it(self) -> None:
        result = self.record(
            "loose",
            correct="false",
            task_id="2.1",
            topic_id="kms-encryption",
            domain="resilient",
            topic=None,
            time_spent_seconds=45.0,
            occurred_at="2026-08-28T12:00:00",
        )
        progress = self.memory.get_progress("learner-01")
        self.assertTrue(result["recorded"])
        self.assertEqual(result["task_id"], "1.3")
        self.assertEqual(result["domain"], "secure")
        self.assertEqual(len(result["corrections"]), 2)
        self.assertEqual(progress["total_attempts"], 1)
        self.assertEqual(progress["overall_accuracy_percent"], 0.0)

    def test_attempt_inherits_activity_type_from_its_session(self) -> None:
        self.memory.start_session(
            "learner-01", "s-1", "e-1", activity_type="diagnostic", mode="diagnostic"
        )
        inherited = self.record("inherits", session_id="s-1", activity_type=None)
        overridden = self.record("defers", session_id="s-1", activity_type="quiz")
        self.assertEqual(inherited["activity_type"], "diagnostic")
        self.assertEqual(overridden["activity_type"], "diagnostic")
        self.assertEqual(self.memory.get_session("learner-01", "s-1")["answered"], 2)

    def test_attempt_is_idempotent_by_learner_event_id(self) -> None:
        first = self.record("attempt-1", correct=False)
        second = self.record("attempt-1", correct=False)
        progress = self.memory.get_progress("learner-01")
        self.assertTrue(first["recorded"])
        self.assertFalse(second["recorded"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["attempt_id"], second["attempt_id"])
        self.assertEqual(progress["total_attempts"], 1)

    def test_progress_tracks_tasks_topics_recency_and_confidence(self) -> None:
        self.record(
            "attempt-1",
            correct=False,
            difficulty="challenging",
            confidence="high",
            misconception="Treated an SCP as a permission grant",
            occurred_at="2026-08-28T12:00:00-05:00",
        )
        progress = self.memory.get_progress("learner-01")
        secure = next(item for item in progress["domains"] if item["id"] == "secure")
        task = next(item for item in secure["tasks"] if item["id"] == "1.1")
        topic = next(item for item in task["topics"] if item["id"] == "iam-policy-evaluation")
        self.assertEqual(progress["overall_accuracy_percent"], 0.0)
        self.assertEqual(progress["evidence_status"], "insufficient")
        self.assertEqual(progress["confidence_calibration"]["overconfident_errors"], 1)
        self.assertEqual(task["attempts"], 1)
        self.assertEqual(topic["misconceptions"][0]["count"], 1)

    def test_scenario_rubric_is_separate_from_objective_accuracy(self) -> None:
        self.record("objective", correct=True)
        self.record(
            "scenario",
            correct=False,
            activity_type="scenario",
            response_type="scenario",
            rubric={"requirements": 3, "security": 2, "tradeoffs": 1},
        )
        progress = self.memory.get_progress("learner-01")
        self.assertEqual(progress["total_attempts"], 1)
        self.assertEqual(progress["overall_accuracy_percent"], 100.0)
        self.assertEqual(progress["scenario_evaluations"], 1)
        self.assertEqual(progress["scenario_rubric_average"]["security"], 2.0)

    def test_new_learner_recommendation_is_diagnostic_and_profile_aware(self) -> None:
        self.memory.set_profile("learner-01", target_exam_date="2026-09-05", weekly_hours=4, session_minutes=30)
        recommendation = self.memory.get_recommendation("learner-01")
        self.assertEqual(recommendation["recommended_activity"], "diagnostic")
        self.assertEqual(recommendation["session_steps"][-1]["questions"], 14)
        self.assertGreaterEqual(recommendation["schedule"]["recommended_sessions_per_week"], 1)
        self.assertIn("urgency", recommendation["schedule"])

    def test_recommendation_prioritizes_untouched_weighted_domain(self) -> None:
        self.record("secure-sample")
        recommendation = self.memory.get_recommendation("learner-01")
        self.assertEqual(recommendation["recommended_domain"], "resilient")
        self.assertEqual(recommendation["evidence_status"], "unsampled")

    def test_diagnostic_session_covers_all_tasks_and_withholds_active_score(self) -> None:
        session = self.memory.start_session(
            "learner-01", "diagnostic-1", "session-start-1", "diagnostic", "diagnostic"
        )
        duplicate = self.memory.start_session(
            "learner-01", "different-id", "session-start-1", "diagnostic", "diagnostic"
        )
        self.assertEqual(session["target_questions"], 14)
        self.assertEqual(len(session["task_plan"]), 14)
        self.assertIsNone(session["score"])
        self.assertTrue(duplicate["duplicate"])
        self.record("diag-answer", activity_type="diagnostic", session_id="diagnostic-1")
        active = self.memory.get_session("learner-01", "diagnostic-1")
        self.assertEqual(active["coverage_by_task"]["1.1"], 1)
        self.assertIsNone(active["score"])
        completed = self.memory.complete_session("learner-01", "diagnostic-1")
        self.assertEqual(completed["score"]["correct"], 1)

    def test_session_normalizes_activity_and_mode_synonyms(self) -> None:
        baseline = self.memory.start_session("learner-01", "diag-base", "event-b", "diagnostic", "baseline")
        self.assertEqual(baseline["activity_type"], "diagnostic")
        self.assertEqual(baseline["target_questions"], 14)
        diag_full = self.memory.start_session("learner-01", "diag-f", "event-f", "diagnostic_assessment", "full")
        self.assertEqual(diag_full["activity_type"], "diagnostic")
        self.assertEqual(diag_full["target_questions"], 14)

    def test_mock_plans_use_official_weight_distribution(self) -> None:
        mini = self.memory.start_session("learner-01", "mini", "mini-start", "mock", "mini")
        full = self.memory.start_session("learner-01", "full", "full-start", "mock", "full")
        self.assertEqual(mini["domain_plan"], {"secure": 6, "resilient": 5, "high-performing": 5, "cost-optimized": 4})
        self.assertEqual(full["domain_plan"], {"secure": 19, "resilient": 17, "high-performing": 16, "cost-optimized": 13})
        self.assertEqual(sum(full["domain_plan"].values()), 65)

    def test_flashcard_recall_hides_answer_and_review_is_idempotent(self) -> None:
        card = self.memory.save_flashcard(
            "learner-01",
            "IAM",
            "What wins policy evaluation?",
            "An explicit deny.",
            "2026-08-28T10:00:00-05:00",
            event_id="card-1",
            task_id="1.1",
            topic_id="iam-policy-evaluation",
        )
        duplicate_card = self.memory.save_flashcard(
            "learner-01", "IAM", "Other prompt", "Other answer", event_id="card-1"
        )
        due = self.memory.get_due_flashcards("learner-01", as_of="2026-08-28T16:00:00Z")
        self.assertNotIn("answer", due[0])
        self.assertEqual(self.memory.get_flashcard_answer("learner-01", card["flashcard_id"])["answer"], "An explicit deny.")
        self.assertTrue(duplicate_card["duplicate"])
        review = self.memory.review_flashcard(
            "learner-01", card["flashcard_id"], "review-1", "good", "2026-08-28T12:00:00-05:00"
        )
        duplicate_review = self.memory.review_flashcard(
            "learner-01", card["flashcard_id"], "review-1", "again", "2026-08-28T13:00:00-05:00"
        )
        self.assertEqual(review["next_due_at"], "2026-08-29T17:00:00+00:00")
        self.assertTrue(duplicate_review["duplicate"])
        self.assertEqual(duplicate_review["rating"], "good")

    def test_flashcard_dates_and_learner_ownership_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "ISO 8601"):
            self.memory.save_flashcard("learner-01", "S3", "Prompt", "Answer", "not-a-date", event_id="bad")
        card = self.memory.save_flashcard("learner-01", "S3", "Prompt", "Answer", event_id="owned")
        with self.assertRaisesRegex(ValueError, "not found"):
            self.memory.get_flashcard_answer("learner-02", card["flashcard_id"])

    def test_misconception_output_is_bounded(self) -> None:
        for index in range(7):
            self.record(f"attempt-{index}", correct=False, misconception=f"Misconception {index}")
        self.assertEqual(len(self.memory.get_progress("learner-01")["misconceptions"]), 5)


class MigrationTests(unittest.TestCase):
    def test_v1_database_is_migrated_additively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "v1.sqlite3"
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE learner_profiles (
                    learner_id TEXT PRIMARY KEY, target_exam_date TEXT, weekly_hours REAL,
                    session_minutes INTEGER, preferences TEXT, updated_at TEXT NOT NULL
                );
                CREATE TABLE quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, learner_id TEXT NOT NULL, domain TEXT NOT NULL,
                    topic TEXT NOT NULL, difficulty TEXT NOT NULL, correct INTEGER NOT NULL,
                    misconception TEXT, occurred_at TEXT NOT NULL
                );
                CREATE TABLE flashcards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, learner_id TEXT NOT NULL, topic TEXT NOT NULL,
                    prompt TEXT NOT NULL, answer TEXT NOT NULL, due_at TEXT NOT NULL, created_at TEXT NOT NULL
                );
                INSERT INTO quiz_attempts
                    (learner_id, domain, topic, difficulty, correct, occurred_at)
                VALUES ('legacy', 'secure', 'IAM', 'standard', 1, '2026-01-01T00:00:00+00:00');
                PRAGMA user_version = 1;
                """
            )
            connection.commit()
            connection.close()
            memory = StudyMemory(database)
            progress = memory.get_progress("legacy")
            self.assertEqual(progress["total_attempts"], 1)
            self.assertEqual(progress["overall_accuracy_percent"], 100.0)
            with sqlite3.connect(database) as migrated:
                self.assertEqual(migrated.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
                columns = {row[1] for row in migrated.execute("PRAGMA table_info(quiz_attempts)")}
            self.assertIn("event_id", columns)
            self.assertIn("task_id", columns)
            result = memory.record_attempt(
                "legacy", "secure", "IAM", "standard", False,
                event_id="new-attempt", task_id="1.1", topic_id="iam-policy-evaluation"
            )
            self.assertTrue(result["recorded"])


if __name__ == "__main__":
    unittest.main()

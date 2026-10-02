---
name: "aws-saa-study-coach"
displayName: "AWS SAA-C03 Study Coach"
description: "Adaptive AWS Certified Solutions Architect - Associate (SAA-C03) study coach with local learner memory, diagnostics, weighted mocks, quizzes, scenario drills, flashcards, and progress tracking"
keywords: ["aws", "saa-c03", "solutions-architect", "aws-certification", "aws-study", "aws-quiz", "mock-exam", "flashcards", "scenario-drill", "study-coach", "well-architected"]
author: "AWS SAA Study Coach contributors"
---

# AWS SAA-C03 Study Coach Power

An adaptive, privacy-first study coach for the **AWS Certified Solutions Architect - Associate (SAA-C03)** examination. It provides 9 specialized study skills powered by a local, persistent learner-memory MCP server with zero third-party dependencies.

> **Privacy Contract:** This Power never stores question stems, option texts, or chat transcripts in persistence. Only structured learning telemetry (domain/task/topic IDs, correctness booleans, difficulty, confidence levels, time spent, misconception tags, and scenario rubric dimensions) is saved, and all of it stays on the learner's machine.
>
> **Adoption reporting:** when a team endpoint is configured, the Power reports *that* a session started and finished — install ID, `username@hostname`, activity type, mode, question counts, duration, version, OS, timestamp. It never transmits `learner_id`, correctness, mastery, domains, topics, misconceptions, rubrics, or flashcard content. Disable it on a machine with `AWS_SAA_TELEMETRY_DISABLED=1`.

---

## Capabilities & Included Skills

This Power equips the agent with 9 dedicated study skills located in `skills/`:

1. **`diagnostic-assessment`**: Establishes an initial evidence baseline with a 14-question diagnostic (exactly 1 question per official task statement) with scoring withheld until completion.
2. **`mock-exam`**: Timed-style mini (20 questions) and full (65 questions) mock exams distributed by official domain weights with answer flagging and delayed scoring.
3. **`quiz-learner`**: Adaptive quizzes of a learner-requested length on requested domains/topics, explaining option-by-option rationales and recording misconceptions.
4. **`scenario-drill`**: Coached architecture scenarios testing design trade-offs against explicit business/technical constraints, evaluated on a 0–4 multidimensional rubric.
5. **`flashcard-review`**: Active-recall spaced repetition flashcard review hiding answers during recall and scheduling reviews with `Again`, `Hard`, `Good`, and `Easy` ratings.
6. **`adaptive-study-plan`**: Builds immediate, time-bounded study sessions based on target exam dates, weekly hours, due flashcards, and lowest-evidence/lowest-mastery tasks.
7. **`review-progress`**: Generates progress reports across all 4 domains, 14 tasks, and 42 topics, highlighting confidence calibration and demonstrated misconceptions.
8. **`teach-topic`**: SAA-C03 deep-dive explanations comparing architectural trade-offs, selection rules, and common AWS service confusions.
9. **`question-quality`**: Audits and gates all practice questions against `docs/question-quality-rubric.md` to ensure complete stems, plausible distractors, and no exam-dump claims.

---

## Question Presentation Contract

Applies to every flow that asks an objective question: `quiz-learner`, `diagnostic-assessment`, and `mock-exam`. A question must not be answerable from anything except its stem and options.

1. **Coverage-free headings.** Head each item with its position only (`Question 4 of 20`). Never name the domain, task, topic, difficulty, or the service under test before the learner answers — a heading such as `Question 16 of 20 — Aurora Global Database` hands over the key when that is an option.
2. **Vary the key's position.** Choose option order so the correct letter moves across the set; in any set of 10 or more, no single position may hold the key in more than about 40% of items.
3. **Balanced options.** Distractors match the key in length, specificity, and detail. The longest or most-qualified option must not be reliably correct.
4. **Format cues stay.** State single-answer or multiple-response, and for multiple-response the exact number to select.

Reveal canonical coverage, difficulty, and the option-by-option rationale **after** grading. The full gate lives in `docs/question-quality-rubric.md`, and `steering/steering.md` delivers it to the agent on every session.

---

## SAA-C03 Exam Blueprint & Taxonomy

The Power implements the official SAA-C03 exam taxonomy (`docs/saa-c03-concept-catalog.json` and `docs/saa-c03-exam-blueprint.md`):

| Domain ID | Domain Title | Exam Weight | Official Task Statements |
| :--- | :--- | :---: | :--- |
| `secure` | Design Secure Architectures | **30%** | **1.1:** Secure access to AWS resources<br/>**1.2:** Secure workloads & applications<br/>**1.3:** Data security controls |
| `resilient` | Design Resilient Architectures | **26%** | **2.1:** Scalable & loosely coupled architectures<br/>**2.2:** Highly available / fault-tolerant architectures |
| `high-performing` | Design High-Performing Architectures | **24%** | **3.1:** High-performing / scalable storage<br/>**3.2:** Elastic & high-performing compute<br/>**3.3:** High-performing databases<br/>**3.4:** High-performing network architectures<br/>**3.5:** High-performing data ingestion & transformation |
| `cost-optimized` | Design Cost-Optimized Architectures | **20%** | **4.1:** Cost-optimized storage<br/>**4.2:** Cost-optimized compute<br/>**4.3:** Cost-optimized databases<br/>**4.4:** Cost-optimized network architectures |

---

## MCP Server (`study-memory`)

Defined in `mcp.json` and implemented in `study-memory-mcp/server.py` via standard-library Python stdio JSON-RPC 2.0.

### Available Tools (13)

- **`get_exam_catalog`**: Look up canonical domains, tasks, topics, selection rules, and common confusions.
- **`set_learner_profile`**: Set/update target exam date, weekly study hours, session length, and preferences.
- **`get_learner_profile`**: Retrieve saved learner profile.
- **`start_study_session`**: Start a diagnostic, weighted mock, quiz, or scenario session.
- **`get_study_session`**: Retrieve active session coverage (scores withheld during progress).
- **`complete_study_session`**: Complete a study session and get final results.
- **`record_quiz_attempt`**: Record an objective attempt or scenario rubric with `event_id` idempotency. Pass `topic_id`; it determines `task_id` and `domain`, and a conflicting parent, an activity that disagrees with its session, or a stray argument is corrected and reported rather than rejected.
- **`get_progress`**: Get mastery summary, evidence statuses, recency decay, and confidence calibration.
- **`get_study_recommendation`**: Get profile-, deadline-, due-card-, and evidence-calibrated study advice.
- **`save_flashcard`**: Save a learner-owned recall card with topic and prompt.
- **`get_due_flashcards`**: Retrieve due cards with answers omitted to force active recall.
- **`get_flashcard_answer`**: Fetch the answer only after the learner provides their recall attempt.
- **`review_flashcard`**: Grade recall (`again`/`hard`/`good`/`easy`) and update spaced-repetition schedule.

---

## Quick Start & Usage Examples

### 1. Initial Diagnostic Baseline
```text
"Start the 14-question SAA-C03 diagnostic for learner miguel and withhold feedback until completion."
```

### 2. Set Study Target & Preferences
```text
"Set my exam date to 2026-11-15 with 5 hours per week and 30-minute sessions for learner miguel."
```

### 3. Adaptive Study Recommendation
```text
"What should learner miguel study today?"
```

### 4. Topic Explanation & Quizzes
```text
"Teach me Amazon Aurora Global Database vs. RDS Read Replicas for SAA-C03."
"Quiz learner miguel on Domain 1: Design Secure Architectures with 3 standard questions."
```

### 5. Timed Mini or Full Mock Exam
```text
"Start a 20-question SAA-C03 mini mock for learner miguel."
"Start a 65-question full SAA-C03 mock for learner miguel."
```

### 6. Architecture Scenario Drill
```text
"Give me an SAA-C03 scenario about multi-tier resilient architecture. Let me design it before you grade."
```

### 7. Spaced Repetition Flashcards
```text
"Create a flashcard for learner miguel on the difference between Gateway and Interface VPC Endpoints."
"Review my due flashcards for learner miguel."
```

---

## Local Database Location

The learner SQLite database defaults to:
```text
~/.kiro/aws-saa-study-coach/study-memory.sqlite3
```
You can override the database path by setting the `AWS_SAA_STUDY_DB` environment variable.

The same file holds the adoption-telemetry outbox (`telemetry_outbox`, `telemetry_state`). Those tables are additive and sit outside the learner-memory schema, so `PRAGMA user_version` stays at `2`.

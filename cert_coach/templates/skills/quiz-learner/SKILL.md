---
name: quiz-learner
description: Run original SAA-C03 quizzes with canonical coverage, strict question-quality checks, idempotent recording, and adaptive follow-up.
---

# Run an adaptive SAA-C03 quiz

Use this skill when a learner asks for practice questions, submits an answer, or requests quiz review.

## Before the first question

1. Resolve `learner_id` (`default` only when none is supplied). Call `get_learner_profile`, `get_progress`, and `get_study_recommendation`.
2. Use the requested area or the recommendation's canonical `domain`, `task_id`, and `topic_id`. Call `get_exam_catalog` for that task.
3. For a multi-question quiz, create stable session and start-event IDs and call `start_study_session` with `activity_type: quiz`, `mode: custom`, and the requested count. Reuse the same IDs on retries.
4. Create only original practice. Never use remembered, leaked, or purported live AWS exam items.

## Per-question workflow

1. Give each question a stable question ID and attempt event ID. Do not reuse an attempt event ID for a different question.
2. Internally apply `docs/question-quality-rubric.md` before asking, including the presentation-neutrality gate: vary which option letter holds the key across the set instead of settling on one. Reject or rewrite the question if more than one answer is defensible.
3. Head each question with its position only (`Question 4 of 20`). Do not name the domain, task, topic, difficulty, or the service under test before the learner answers — a heading such as `Aurora Global Database` gives away the key. State only whether it is single-answer or multiple-response, and for multiple-response exactly how many options to choose.
4. Include enough constraints to identify the best design: availability, latency, security, operations, cost, migration, recovery, or data characteristics.
5. Wait for the learner's answer before revealing feedback. Ask for low/medium/high confidence when it will not disrupt the requested format.
6. Grade against the stated requirements. Reveal the domain, task, topic, and difficulty here, with the answer, never before it. Explain the best answer and why every distractor fails a specific requirement. If a service fact remains uncertain, verify against an official catalog reference or disclose the uncertainty instead of recording a grade.
7. Call `record_quiz_attempt` exactly once with the stable event ID, canonical IDs, `activity_type: quiz`, response type, strict boolean correctness, optional confidence, flag, and a concise misconception only when demonstrated. Include timing only if actually measured; never invent it.

After the final question, call `complete_study_session` when a session was opened, summarize evidence without predicting a pass, and call `get_study_recommendation` for the next action.

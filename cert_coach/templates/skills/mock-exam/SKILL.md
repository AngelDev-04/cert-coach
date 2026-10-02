---
name: mock-exam
description: Run timed-style original SAA-C03 mini or full mock sessions with official domain weighting, flags, delayed feedback, and resumable coverage.
---

# Run an SAA-C03 mock session

**Pacing (mandatory): ONE question per message. Present it, then STOP and wait for the learner's reply. Do NOT output Question 2 in the same message as Question 1.**

## Modes

- `mini`: 20 original questions for routine mixed practice.
- `full`: 65 original questions for exam-style endurance.
- `custom`: 5–65 questions only when the learner asks for a specific count.

## Workflow

1. Resolve `learner_id`, explain the selected length, and state that the content is original and the result does not predict passing. A 65-question practice session grades all practice items for feedback; it does not attempt to identify or reproduce the real exam's 15 unscored items.
2. Create stable session/start IDs and call `start_study_session` with `activity_type: mock` and the selected mode. Follow its `domain_plan`; on resume, call `get_study_session` and use `coverage_by_domain` to fill remaining quotas.
3. Within each domain, rotate across official tasks and canonical topics from `get_exam_catalog`. Do not repeatedly test one familiar service while leaving task statements untouched.
4. Question loop (for i = 1..N): present only `Question i of N`, then end your message and STOP until the learner replies. Write each question only when it is its turn, using `docs/question-quality-rubric.md`. Mix single-answer and clearly labeled multiple-response items; for multiple-response, state exactly how many answers to select. Apply the presentation-neutrality gate: number each item without naming its domain, task, topic, or tested service, and vary which option letter holds the key across the session.
5. Accept an answer, optional low/medium/high confidence, and an optional learner flag. Grade silently and call `record_quiz_attempt` with stable IDs, `activity_type: mock`, session coverage, response type, strict correctness, confidence, and flag. Do not reveal correctness during the active mock: reply with only `Answer recorded.` plus the next question.
6. Do not claim to enforce a timer unless elapsed time is actually available. Store `time_spent_seconds` only when measured, never estimated.
7. After the target count—or explicit early termination—call `complete_study_session`. Then provide explanations, flagged-item review, domain/task evidence, misconceptions, confidence calibration, and `get_study_recommendation`.

Never describe generated questions as official, leaked, remembered from an exam, or equivalent to an AWS score report.

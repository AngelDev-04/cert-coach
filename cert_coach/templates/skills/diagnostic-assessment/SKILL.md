---
name: diagnostic-assessment
description: Establish an evidence-limited SAA-C03 baseline with one original question for each of the 14 official task statements.
---

# Run the SAA-C03 diagnostic

Use this for first-time learners or explicit baseline requests.

1. Resolve `learner_id`, load the profile and progress, and explain that one item per task samples coverage but cannot prove mastery or predict passing.
2. Generate stable session/start IDs and call `start_study_session` with `activity_type: diagnostic` and `mode: diagnostic`. The returned plan contains all 14 task IDs.
3. For each still-unanswered task, call `get_exam_catalog`, choose one canonical topic, and create one original standard-difficulty question that passes `docs/question-quality-rubric.md`.
4. Ask one question at a time, headed by its number alone; naming the sampled task or topic would reveal the key, and vary which option letter is correct across the 14 items. State single-answer or the exact multiple-response count. Collect the answer and low/medium/high confidence. Do not reveal correctness or explanations until the diagnostic ends, so earlier teaching does not contaminate later baseline items.
5. Silently grade each answer and call `record_quiz_attempt` with stable attempt/question IDs, `activity_type: diagnostic`, the session ID, canonical coverage, confidence, and a concise demonstrated misconception. Never invent timing.
6. Support continuation by calling `get_study_session` and using `coverage_by_task`; question text is not persisted, so generate a fresh original item for each remaining task.
7. After all items—or when the learner explicitly ends early—call `complete_study_session`. Review answers by selection rule, then show sampled/unsampled tasks, confidence-calibration observations, and the next recommendation.

Always call the result a diagnostic baseline, not a mock score, readiness score, or pass prediction.

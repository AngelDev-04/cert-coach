---
inclusion: always
---

# AWS SAA-C03 Study Coach steering

This Power creates original practice material. It never claims that a generated item is official, leaked, remembered from a real exam, or predictive of a pass.

## Question presentation contract

Applies to every flow that asks the learner an objective question: quizzes, diagnostics, and mock sessions.

A question must not be answerable from anything except the stem and its options.

1. **Coverage-free headings.** Head each item with its position only — `Question 4 of 20`. Never name the domain, task, topic, difficulty, or the service under test before the learner answers. A heading such as `Question 16 of 20 — Aurora Global Database` hands over the key when `Aurora Global Database` is an option.
2. **Vary the key's position.** Choose option order so the correct letter moves across the set. In any set of 10 or more, no single position may hold the key in more than about 40% of items. A set where most answers are `B` is guessable without knowledge and produces worthless evidence.
3. **Balanced options.** Every distractor gets the same length, specificity, and grammatical detail as the key. The longest or most-qualified option must not be reliably correct.
4. **Format cues stay.** State single-answer or multiple-response, and for multiple-response the exact number to select. That is a format cue, not a coverage cue.

Reveal the canonical domain, task, topic, difficulty, and the option-by-option rationale **after** grading, where it supports review instead of guessing.

Ambiguity and integrity checks in `docs/question-quality-rubric.md` still apply; presentation neutrality is in addition to them, not a replacement.

## Recording

Record every objective attempt with `record_quiz_attempt` using a stable `event_id` and the canonical `topic_id`. Never store question stems, option text, or transcripts — only structured telemetry. Never invent timing; send `time_spent_seconds` only when it was actually measured.

---
name: adaptive-study-plan
description: Turn SAA-C03 learner evidence, available time, exam date, and due recall into an immediately executable study session.
---

# Build and run an adaptive study session

1. Resolve `learner_id`. Call `get_learner_profile`, `get_progress`, `get_due_flashcards`, and `get_study_recommendation`.
2. If profile information is absent, ask only for useful missing fields: target date, weekly hours, session minutes, and learning preferences. Save supplied values.
3. Use the recommendation's structured `session_steps`; do not replace an unsampled task with a supposed weakness. Explain briefly why the task was selected and its evidence status.
4. Offer a one-line plan with exact minutes, due-card count, question count, canonical task/topic, and activity type.
5. On confirmation, invoke the matching workflow: flashcard review first when allocated, then diagnostic, targeted quiz, scenario, or mock. Follow that workflow's loop exactly: ONE question per message, then STOP and wait for the learner's reply.
6. At the end, refresh progress and recommendation. Report what evidence changed, not merely the session score.
7. If the target date is close, prioritize mixed retrieval and timed-style practice while still repairing high-impact misconceptions. If the date has passed, ask to update it.

Never convert local practice accuracy into a probability of passing. Keep recommendations actionable, evidence-calibrated, and within the learner's saved time budget.

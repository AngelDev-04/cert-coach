---
name: review-progress
description: Explain evidence-calibrated SAA-C03 progress and build a concrete profile-, deadline-, and spaced-review-aware next session.
---

# Review learner progress

1. Resolve `learner_id`; use `default` only when none is available.
2. Call `get_learner_profile`, `get_progress`, `get_due_flashcards`, and `get_study_recommendation`.
3. If the profile is missing, ask for the target exam date, weekly study hours, preferred session length, and optional learning preferences; save supplied values with `set_learner_profile`.
4. If no objective attempts exist, recommend the diagnostic workflow rather than labeling any domain weak.
5. Present a compact report:
   - objective attempts, recent evidence, and evidence status;
   - domain/task/topic coverage and recency-weighted mastery;
   - recurring misconceptions and confidence-calibration patterns;
   - scenario rubric trends separately from objective accuracy;
   - due flashcard count;
   - the recommendation's time-bounded session steps and deadline context.
6. Treat fewer than three attempts at a task as insufficient evidence. Never infer mastery from one item or imply that stored performance predicts passing.
7. Offer to start the recommended diagnostic, flashcard review, targeted quiz, scenario, or mock workflow immediately.

When profile details change, call `set_learner_profile`. Do not display stored learner information unrelated to the requested progress review.

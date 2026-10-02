---
name: flashcard-review
description: Run answer-hidden SAA-C03 active recall and schedule learner-owned cards with Again, Hard, Good, or Easy ratings.
---

# Review due flashcards

1. Resolve `learner_id` and call `get_due_flashcards`. This tool intentionally returns prompts without answers.
2. Present one prompt at a time and wait for an attempted answer. Never call or reveal `get_flashcard_answer` before the learner attempts recall.
3. After the attempt, call `get_flashcard_answer`. Compare the learner's response to the essential selection rule rather than demanding exact wording.
4. Ask the learner to self-rate, or recommend a rating and let them confirm:
   - `again`: incorrect or no meaningful recall;
   - `hard`: substantially correct but effortful or incomplete;
   - `good`: correct with normal effort;
   - `easy`: immediate, complete, and confident recall.
5. Call `review_flashcard` with a new stable event ID. Reuse that ID if retrying the same review. Tell the learner the next due date without implying that interval length proves mastery.
6. Continue up to the requested count or the recommendation's review allocation, then call `get_study_recommendation` if the learner wants another activity.

Cards are learner-owned study aids. Keep prompts atomic, test one decision rule, and avoid copying proprietary or live exam content.

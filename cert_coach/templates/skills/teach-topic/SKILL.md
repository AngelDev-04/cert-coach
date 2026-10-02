---
name: teach-topic
description: Teach an AWS service or architecture concept at SAA-C03 depth using canonical exam tasks, selection rules, and learner evidence.
---

# Teach an SAA-C03 topic

Use this skill for explanations, comparisons, or study guides about SAA-C03 topics.

1. Read `docs/saa-c03-exam-blueprint.md`. Call `get_exam_catalog` to map the request to one canonical `domain`, `task_id`, and `topic_id`; use the catalog's selection rules and common confusions.
2. When a `learner_id` is available, call `get_learner_profile` and `get_progress`. Mention prior evidence only when it improves the lesson. Treat fewer than three objective attempts as insufficient evidence, not weakness.
3. Explain in this order: requirement to recognize, selection rule, small architecture example, closest alternatives, common confusion, and one retrieval question.
4. Compare similar choices using exam-relevant constraints such as availability scope, connection model, access pattern, consistency, RTO/RPO, latency, security, operational effort, and cost.
5. **Pacing: ONE question per message.** End your message right after the retrieval question and STOP. Reveal the answer only after the learner replies. Optionally ask for low/medium/high confidence to expose calibration gaps.
6. Be precise about AWS behavior. If a current-service detail is uncertain, say so and direct the learner to the catalog's official AWS reference rather than guessing.
7. Never present generated content as official AWS training, a live exam item, or a substitute for AWS documentation.

End by offering a targeted quiz or scenario. If the learner opts into a flashcard, call `save_flashcard` with the canonical task/topic IDs and a new stable `event_id`; reuse that ID if the call is retried.

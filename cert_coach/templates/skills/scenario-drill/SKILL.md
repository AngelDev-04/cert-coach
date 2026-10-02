---
name: scenario-drill
description: Coach original SAA-C03 architecture scenarios with a separate multidimensional rubric instead of mixing them into quiz accuracy.
---

# Run an SAA-C03 scenario drill

1. Resolve the learner and call `get_learner_profile`, `get_progress`, and `get_study_recommendation`.
2. Choose one or two canonical tasks with `get_exam_catalog`, preferring unsampled or recommended areas unless the learner specifies a topic.
3. Create stable session/start/attempt IDs. Call `start_study_session` with `activity_type: scenario`, `mode: custom`, and one target item.
4. Present business requirements and constraints, not the solution. Include enough relevant dimensions for a defensible design: scale, availability, data, security, latency, recovery, cost, migration, and operations.
5. Ask the learner to propose an architecture and justify trade-offs before coaching.
6. Review the response against only applicable rubric dimensions, each scored 0–4: requirements, service selection, resilience, security, cost, and trade-offs. Explain satisfied requirements, risks, a stronger design, and reusable selection rules.
7. Call `record_quiz_attempt` with `activity_type: scenario`, `response_type: scenario`, canonical IDs, the rubric, and a strict `correct` boolean indicating whether core material requirements were met. Scenario results are coaching evidence and must not be presented as objective quiz accuracy.
8. Complete the session and recommend a related retrieval question or flashcard.

Never present a generated scenario as leaked, official, or predictive of an AWS exam result.

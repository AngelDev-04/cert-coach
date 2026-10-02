"""Shared turn-taking (pacing) rules injected into every harness's instruction files.

Kept short and imperative on purpose: smaller models follow terse, direct rules
far more reliably than long prose. Keep this text in sync with the static copies
in ``cert_coach/templates/steering/steering.md``, ``templates/POWER.md`` and the
``templates/skills/*/SKILL.md`` files.
"""

from __future__ import annotations

# Exact phrase asserted by tests; every question-asking artifact must contain it.
ONE_QUESTION_RULE = "ONE question per message"

TURN_TAKING_CONTRACT = """## Turn-Taking Contract (highest priority)
Applies to EVERY flow that asks the learner something: quiz, diagnostic, mock, flashcards, teach retrieval check, scenario.

1. **ONE question per message.** Each assistant message contains exactly one question (or one flashcard prompt). After the answer prompt, STOP and end your turn.
2. **Wait for the reply.** Send the next question only after the learner's reply arrives and, in immediate-feedback flows, after it is graded and recorded with `record_quiz_attempt`.
3. **No batching.** Never pre-generate, preview, list, or batch upcoming questions. Never answer or simulate a reply on the learner's behalf.
4. **Delayed-scoring flows (diagnostic, mock).** Still ONE question per message. After each reply, record it silently, say only `Answer recorded.`, then present the next question. No feedback.

Anti-example: a message that contains both `Question 1 of 5` and `Question 2 of 5` violates this contract.
"""

PACING_LINE = (
    "**Pacing (mandatory): ONE question per message. Present it, then STOP and wait "
    "for the learner's reply. Do NOT output Question 2 in the same message as Question 1.**"
)

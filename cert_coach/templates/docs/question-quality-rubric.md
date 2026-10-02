# SAA-C03 original-question quality rubric

Use this rubric before presenting or grading any generated practice question. It applies to quizzes, diagnostics, and mock sessions. This Power creates independent practice material and never claims that a generated item is official or appeared on an AWS exam.

## Release gate

A question is **ready** only when every required check passes. Rewrite a **revise** item before showing it. Do not grade a **reject** item.

| Check | Ready criterion | Reject or revise when |
| --- | --- | --- |
| Canonical scope | Maps to one catalog domain, task ID, and primary topic ID | Coverage is outside the current catalog or only trivia |
| Decision being tested | Tests an architecture selection rule under explicit requirements | Tests an arbitrary limit, console location, or memorized wording without design value |
| Factual support | Correct answer and rationale agree with the catalog and linked official AWS documentation | A current service behavior is uncertain or unsupported |
| Complete stem | Includes all constraints needed to decide: relevant scale, availability, security, latency, recovery, operations, data, migration, or cost | The answer depends on an unstated assumption |
| Answer cardinality | Exactly one defensible best answer, or exactly the stated number for multiple-response | Several answers satisfy the same requirements or the selection count is hidden |
| Best-answer rationale | Explains why the answer best meets every material requirement | Merely says that a service is "best practice" |
| Distractor quality | Every distractor is plausible, maps to a specific misconception, and fails a stated requirement | Joke options, syntax tricks, overlapping answers, or options unrelated to the stem |
| Language | Concise, neutral, grammatically clear, and free of accidental clues | Absolutes, unequal option detail, or wording that reveals the key |
| Presentation neutrality | The stem, the options, and everything rendered around them — headings, labels, option order — reveal nothing the learner should have to derive | A heading names the tested topic or service, the key sits in a predictable position across a set, or a coverage/difficulty label narrows the field before the answer |
| Exam integrity | Clearly original when provenance matters; no dump, leak, recall, or official-item claim | Requests or claims involving live or proprietary exam content |
| Feedback safety | Explanation distinguishes service choices and admits unresolved uncertainty | Invents AWS behavior or records a grade despite ambiguity |

## Internal authoring template

Before presenting the item, determine:

1. Canonical `domain`, `task_id`, and `topic_id`.
2. One selection rule the learner must apply.
3. Material requirements in the stem.
4. Correct option(s) and why each requirement is met.
5. For each distractor: the diagnosed misconception and failed requirement.
6. Response type and explicit number of selections.
7. Difficulty:
   - `foundation`: one primary selection rule and minimal competing constraints;
   - `standard`: combines at least two relevant constraints;
   - `challenging`: requires prioritizing several plausible designs without relying on obscure trivia.

8. Presentation: a coverage-free heading (`Question 4 of 20`), and an option order chosen so the key's position varies across the set rather than settling on one letter.

Do not expose hidden chain-of-thought. Learner feedback should contain the answer, concise rationale, option-by-option analysis, the reusable selection rule, and any demonstrated misconception.

## Scenario rubric

Score only applicable dimensions from 0–4 and explain observable evidence:

- `requirements`: identifies and satisfies material business and technical requirements;
- `service_selection`: chooses services whose documented behavior fits the access and operating model;
- `resilience`: addresses failure boundaries, recovery, and removal of single points of failure;
- `security`: applies least privilege, network/data protection, and appropriate controls;
- `cost`: recognizes meaningful cost drivers and avoids unjustified expense;
- `tradeoffs`: explains what is gained, sacrificed, and why the design fits the stated priorities.

Scenario rubric scores remain separate from objective-question accuracy.

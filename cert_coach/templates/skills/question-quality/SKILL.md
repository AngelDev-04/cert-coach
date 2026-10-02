---
name: question-quality
description: Audit or improve an original SAA-C03 practice question for scope, factual support, ambiguity, distractor quality, and exam integrity.
---

# Review SAA-C03 question quality

Use this when creating a question or when a learner asks whether a practice item is fair or ambiguous.

1. Map the tested decision to one canonical domain, task, and topic with `get_exam_catalog`.
2. Apply every applicable item in `docs/question-quality-rubric.md` without exposing hidden chain-of-thought. Return concise findings and a corrected item when needed.
3. Verify that all needed constraints appear in the stem and exactly one best answer exists, or exactly the stated number for multiple-response.
4. For each distractor, name the plausible misconception it diagnoses and the stated requirement it fails. Remove joke, trivia-only, overlapping, or obviously malformed options.
5. Verify service claims against the local catalog and its official AWS reference. If current behavior remains uncertain, flag the item as unsuitable for grading rather than guessing.
6. Audit presentation as well as content. A heading that names the tested topic or service, a pre-answer difficulty or coverage label, or a set whose key sits on one option letter is a `revise` finding even when the stem itself is clean.
7. Check that the question is original and contains no claim of being copied from or appearing on the AWS exam.
8. Do not record a learner attempt for a question that fails the rubric. Rewrite it first, then ask for the learner's answer.

Output: canonical coverage, verdict (`ready`, `revise`, or `reject`), concise issues, corrected stem/options when applicable, answer rationale, and distractor diagnoses.

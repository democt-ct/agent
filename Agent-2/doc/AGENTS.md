# Codex Project Instructions

These instructions apply whenever Codex works in this repository.

## Requirement Handling

- Start from the user's original request. Do not assume the user has already fully clarified the goal, constraints, scope, or implementation path.
- Ask a clarification question only when the request contains a key ambiguity and different interpretations would lead to meaningfully different solutions or high rework cost.
- When clarification is not necessary, proceed with the most reasonable interpretation and state any important assumptions briefly.

## Scope Control

- Design and implement around the user's explicitly stated goal.
- Do not expand the business objective, introduce alternative product directions, or add unrelated workflows unless the user asks for them.
- Prefer the smallest complete solution that satisfies the goal.
- If the shortest path would introduce structural problems, choose the smallest correct solution instead.

## Implementation Principles

- Avoid patchwork compatibility layers, fallback branches, or broad defensive designs that are unrelated to the current requirement.
- Add only the input constraints, state checks, and boundary protections needed to keep the logic complete and reliable.
- Follow the existing project architecture, naming, and data flow before introducing new abstractions.
- Keep edits tightly scoped. Do not refactor unrelated files or change behavior outside the requested surface.

## Reasoning Checklist

Before proposing or making a change, check the full path:

- Input: what data, parameters, or user actions enter the flow.
- Processing: how the request is interpreted, transformed, and validated.
- State: what database records, in-memory objects, or UI state may change.
- Output: what response, artifact, or visible behavior should result.
- Downstream impact: what callers, screens, tests, or future operations may be affected.

## Accuracy And Communication

- Mark assumptions and unverified premises clearly.
- Do not present inference as confirmed fact.
- If something cannot be verified locally, say what was checked and what remains uncertain.
- Prefer concise, concrete engineering language over broad conceptual explanations.

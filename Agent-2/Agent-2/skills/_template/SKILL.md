---
name: your-skill-name
description: One-sentence description of what this skill does and when it should be used.
user-invocable: true
allowed-tools: "Read Write Edit Bash Glob Grep"
---

# Your Skill Name

Briefly explain the skill's job in one or two sentences.
Focus on what the skill is responsible for, not product background.

## When To Use

Use this skill when:
- The user explicitly asks for this skill by name.
- The task clearly matches this skill's scope.
- The work benefits from a repeatable workflow.

Do not use this skill when:
- The request is a small one-off change.
- Another installed skill is a better match.
- The task does not need the extra process defined here.

## Inputs

This skill expects:
- A clear user goal.
- Relevant project files or directories.
- Any required env vars, API keys, or local tools.

If key information is missing, first inspect the local repo and make reasonable assumptions.
Only ask the user when the missing detail is actually blocking or risky.

## Outputs

This skill should usually produce:
- A concrete result, not just analysis.
- File changes when appropriate.
- A short summary of what changed.
- Any important assumptions, risks, or next steps.

## Workflow

Follow this sequence:

1. Inspect the local context before making decisions.
2. Identify the smallest viable path to the user's goal.
3. Reuse existing files, patterns, and scripts where possible.
4. Make the required changes.
5. Validate the result with the lightest useful check.
6. Report outcome, assumptions, and anything still not verified.

## Rules

- Prefer modifying existing code over creating parallel implementations.
- Keep changes scoped to the user's request.
- Do not introduce new dependencies unless they are justified.
- Preserve existing conventions unless the user asks for a redesign.
- If you hit repeated failure, change approach instead of retrying blindly.

## File Conventions

If this skill depends on specific files, define them here:
- `path/to/input-file`
- `path/to/config-file`
- `path/to/output-file`

If none are required, remove this section in the real skill.

## Validation

Before finishing:
- Run relevant tests, type checks, or linters if available.
- If validation was not run, say so explicitly.
- Confirm any created output is in the expected format.

## Example Triggers

Users might invoke this skill with prompts like:
- `Use your-skill-name to ...`
- `Please use $your-skill-name for this task`
- `Help me with ...` when the request clearly matches this workflow

## Custom Notes

Put skill-specific instructions here, for example:
- Prompt formats
- Parsing rules
- Output schema requirements
- Safety constraints
- Domain-specific heuristics

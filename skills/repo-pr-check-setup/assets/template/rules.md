# {{REPO}} PR check rules

Rules for `/{{LABEL}}`. Rules owners: {{OWNERS_MD}} (see `CODEOWNERS`). Change these
only through a rules PR (`/{{LABEL}} consolidate`); propose changes as feedback
issues. Every rule has an ID, a reason, and a source. See
`references/learning.md` for the format.

## Principles

<!-- Team-wide stances that beat generic best practice. A finding that contradicts
     one is dropped or reframed. -->
{{PRINCIPLES}}

## Risk priorities

<!-- What this team treats as high-stakes. Risk voters score every finding 1-5 using
     this section first; fixes scored 4 or 5 need the developer's sign-off. -->
{{RISK_PRIORITIES}}

## Rules

<!-- Grouped by area. Each says what is Fix with AI / Surface / Note / Dropped. -->
{{RULES}}

## Code checks

<!-- The team's linter and import preferences, each with an ID and a reason. The rule
     switches themselves live in each tool's config file (named in config.json's
     checks); this section says why, so a rules PR can change both together. -->
{{CODE_CHECKS}}

## Review focus

<!-- What this team wants checked beyond the generic checklist. -->
{{REVIEW_FOCUS}}

## Don't report

{{DONT_REPORT}}

## Issues

{{ISSUES}}

## PR types

<!-- Kinds of PR that need more than the default: how to recognize them, extra
     description sections, and sign-offs. -->
{{PR_TYPES}}

## PR description

{{PR_GUIDANCE}}

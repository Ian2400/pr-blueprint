# Writing findings and issues

## Titles

A title states the problem and its consequence in one line of at most 72
characters. It is never the first sentence of the description cut short.

| Instead of | Write |
|---|---|
| "The row-count check compares parsed rows with every line in the raw file and..." | Row-count check runs after load, so duplicates pile up on rerun |
| "`file_types[file_type][fieldnames]` uses the undefined bare name..." | `--reload` crashes: undefined name `fieldnames` in parse step |
| "Copy-paste error: the wifi_telemetry_data_load_tracking DDL runs its ALTER..." | Tracking table grants and owner applied to the wrong table |

Name the thing (function, table, script) and what goes wrong for the user of the
code. Leave out "Bug:", severity words, and trailing periods.

## Finding body (shown to the developer)

Two to four sentences:

1. What the code does now, with `file:line`.
2. When it goes wrong: the concrete input or situation, and the result.
3. **Impact:** who or what is affected now. If nothing in this change uses the
   affected value, say "No current impact: <thing> isn't used downstream yet."
4. For edge cases, start with **Edge case:** and say how rare it is.

For Surface items, add the suggested fix, or the options when there are several,
each in one line.

## Work issue (Phase 0)

The issue for the work a branch does: what's being built or changed, and why. Keep
it short; it's a record, not a spec.

Title: what the work delivers, at most 72 characters, in the repo's usual style
(for example "Retention: churn model for the 2026 cohort").

```markdown
## Why
<Who asked for this and the problem it solves, in one to three sentences: a
client request, a bug report, planned work.>

## What
<What the branch delivers, as the diff shows it so far: new or changed models,
pipelines, tables, reports. Bullet points.>

## Done when
<How we'll know it's finished: the output exists and is checked, the job runs in
prd, the client has what they asked for.>

---
Opened by `/{{LABEL}}` for branch `<branch>`.
```

Labels: the project's area label and the work type (`feature`, `bug`...), as
`rules.md` says; never create labels. Keep secrets and personal data out.

## GitHub issue body

```markdown
## Problem
<What happens, when, and the result. 2–4 sentences.>

**Location:** `path/to/file.py:123` (branch `<branch>`, commit `<short sha>`)
**Impact:** <current impact, or "No current impact: ...">

## Fix
<For Fix with AI: the fix in one or two sentences.>
<For Surface: "Decision (from @<developer>)": the developer's choice, quoted or
restated, then the fix it implies.>

---
Found by `/{{LABEL}}` on `<branch>` before PR submission.
```

Keep secrets, passwords, tokens, and credential file contents out of issues and
findings. Name the file or variable instead.

## Plan summary (end of Phase 1)

Keep it short, because the details come up one item at a time later. The headline
total is Fix + Surface + Note. Leave out any line that would be empty.

```
PR check for feature/x → master: 14 findings to go through
(4 more were checked and dropped)

  Fix with AI (6)        issues will be filed; 4 agents start now, 2 wait for your sign-off
  Surface to you (5)     2 already tracked (#812, #790), 1 needs your confirmation
  Notes (3)
  Split votes: 3         (the voters didn't agree; marked when you see them)

This PR appears to resolve: #861 (I'll confirm with you before writing "Fixes")

Fix with AI, needs your sign-off (risk 4-5):
  1. [5] Training silently drops rows with NULL target          model_train.sql:103
  2. [4] Dev run overwrites the production embeddings pickle    scoring.py:88

Fix with AI, starting now:
  3. [2] README names the wrong config variable                 README.md:41
  4. ...

High-risk changes (Revert plan entries):
  C2 [5] model_train's feature exclusion logic            not reversible: overwrites retention.features
  C4 [4] nightly scoring script and its model_id

Unclear standard:
  - The connection library's README doesn't say whether cron scripts must use it

Outside this PR (offered as separate issues at the end):
  - shared/db.py still imports the legacy credential helper
```

## Fix with AI items before the issue exists

The developer sees a Fix with AI item as one line in the plan summary. If they ask
for details at the go-ahead question, show the "Problem" and "Fix" sections of the
issue body below. That way, the developer reads the same text they would later see
on GitHub.

## Multiple locations and non-file findings

If the same problem appears in several places (a README, a SQL header, and a work
file all describing the same outdated parameters), make it one finding. Give the
primary location first and list the others on the location line:
`` `a.sql:8` (also `readme.md:14`, `work.sql:6`) ``.

For a finding about the PR description, write the location as "PR #N description".

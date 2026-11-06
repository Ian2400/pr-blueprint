# Learning from feedback

`rules.md` is meant to change as the team uses this skill. Changes flow one way:

```
developer overrides a finding ─┐
reviewer comments on a PR ─────┼─> lesson ─> feedback issue ─> consolidate ─> rules PR ─> CODEOWNERS approve
developer states a convention ─┘
```

Nobody edits `rules.md` directly during a check. Lessons become GitHub issues
labeled with `config.json`'s `feedback_label` (default `pr-check-feedback`). Rules
owners batch them into a rules PR with `consolidate`, and `CODEOWNERS` makes those
owners the required reviewers of anything under `.claude/skills/{{LABEL}}/`.

## Rule format

Every rule in `rules.md` has an ID, so findings, lessons, and later changes can cite
it:

```markdown
- **GP-1: Drop old function signatures with the utility.** <the rule, what's
  Fix with AI / Surface / Note / Dropped under it>.
  *Why:* <the reason>. *Source:* PR #1363, 2026-10-27.
```

IDs are a short area prefix plus a number (`DB-2`, `ENV-1`, `MOD-3`). Never reuse a
retired ID; mark the rule *Retired* with the reason instead of deleting it.

## During a check: recording lessons

Add an entry to the ledger's `lessons` whenever the developer's answer differs from
your triage, or teaches you something the rules don't say:

- They move a planned fix to Surface or Dropped at the go-ahead.
- They drop a Surface item as intentional, or answer "Not a problem here".
- They remove a note as wrong (not merely trivial for this PR).
- They request changes on a fix, or reject it, for a reason beyond this one line.
- They state a convention in their own words ("we always…", "never…").
- They say a PR shouldn't have a work issue. `general` is true when the reason
  names a kind of PR (for example "rules PRs from consolidate"), which the rules
  could list as an exception.
- The developer answers "which is canonical?" (1.2a), or a fix agent added a new
  helper. Propose the `canonical.md` entry it implies (need, use, not, status);
  `general` is true. These are filed and consolidated like rule changes, and
  `consolidate` may edit `canonical.md`.
- A fix agent gets stuck (2.2a). Record the category and risk the voters gave, the
  agent's diagnosis, and what the developer decided. `general` is true when the
  diagnosis names a kind of problem (for example, a fix that needs a schema change)
  that the rules or examples should treat as Surface rather than Fix with AI.
- They disagree with a risk score, or decline to sign off on a fix because it's
  riskier (or safer) than the voters thought. Record the voted risk and theirs: these
  lessons tune `rules.md`'s Risk priorities.
- They choose to amend a rule the PR departs from.
- They answer a security item with "It's a dummy value" or "It's synthetic or
  approved data", or push past one (Phase 3.5). Say what would have stopped the
  false alarm: a "Don't report" path (`target: "rules"`) or an ID pattern change
  (`target: "security_patterns"`). A real secret the scan missed is a lesson too.
- They say a code-check rule, import convention, or tool setting is wrong for the
  team ("we always put SQL keywords in upper case", "that import order fights our
  formatter"), or leave the same rule unpicked with a reason (`target:
  "lint_config"`; name the tool, the rule, and the setting to change). See
  `checks.md`.

```json
{"finding": "F7", "your_category": "fix", "votes": {"category": ["fix", "fix", "surface"], "risk": [2, 3, 2]},
 "developer_action": "dropped as intentional",
 "reason": "<their words>", "general": true, "proposed_rule": "<draft text or null>",
 "rule_id": "<existing rule it touches, or null>", "target": "rules|security_patterns|lint_config"}
```

Security lessons never carry a value or a masked line; give the path, the scan's
rule, and why it's a false alarm. They go into feedback issues, which the whole team
can read.

`general` is true only when the reason would apply to other code ("we always X"), not
when it is about this PR's circumstances ("this script runs once and is deleted").

## End of a run

At Phase 3.6, if any lesson has `general: true`:

1. Draft one proposed rule change per lesson, in the rule format above, with the
   source set to this branch or PR. Merge lessons that say the same thing.
2. Run the conflict check (below).
3. Write the drafts in your message (each in full) and ask, per lesson: **File as feedback** / **Edit first** /
   **Skip**.
4. File each kept one as an issue (see "Feedback issues"). Check open feedback
   issues first; if one already proposes the same thing, add a comment with this
   occurrence instead of a new issue. Repeated occurrences are how owners see what
   matters.

If the developer is listed in `config.json`'s `owners`, also offer to run
`consolidate` now.

## Feedback issues

Title: `Rule proposal: <the rule in a few words>` (72 characters max).
Label: `feedback_label`. If the label doesn't exist, tell the developer to ask a
rules owner to create it; don't create labels.

```markdown
## Proposed change
<new rule / amend <ID> / retire <ID>, in the rule format>

## Evidence
- <PR or branch>, `<file>:<line>`: <what the skill said> → <what the developer or
  reviewer said, quoted or restated>

## Conflicts
<"None found" or the rules it touches and how>

---
Proposed by `/{{LABEL}}`. Rules owners: review with `/{{LABEL}} consolidate`.
```

## `learn <PR#>`: after reviewers comment

Run on a PR that went through review (open or merged). The goal is to catch what
reviewers flagged that this skill missed or got wrong.

1. Fetch the PR's review comments, reviews, and conversation comments:
   `gh api repos/<repo>/pulls/<N>/comments --paginate`,
   `gh api repos/<repo>/pulls/<N>/reviews --paginate`,
   `gh api repos/<repo>/issues/<N>/comments --paginate`.
   Ignore bots, the PR author's own comments (except replies that settle a
   question), and comments that only approve or say thanks.
2. If a ledger for the PR's branch exists, load it, so you know what the skill
   already found and how it was triaged.
3. Classify each remaining comment:
   - **Missed:** a real problem the skill didn't report. Would the checklist or a
     rule have caught it? Propose the checklist focus or rule that would have.
   - **Mis-triaged:** the skill reported it, but the reviewer treated it as more or
     less serious. Propose a rule or calibrated example.
   - **Contradicts a rule:** the reviewer asked for something a rule forbids, or
     objected to something a rule required. Propose amending or retiring the rule.
   - **Missed security item:** a reviewer found a secret, personal data, or a data
     file the scan didn't flag. Tell the developer now, in one line and masked, that
     a pushed secret must be rotated. Then propose the fix: an ID pattern change
     (`target: "security_patterns"`), or, for a credential format no rule catches,
     an engine report (see the end of `consolidate`).
   - **A tool could have caught it:** a style, import, or correctness comment that
     an available linter rule covers (a ruff rule, a sqlfluff rule, a shellcheck
     code) but the team's config doesn't enable. Propose enabling it
     (`target: "lint_config"`), naming the tool, rule, and config file.
   - **One-off:** specific to this PR. No lesson.
   - **Preference:** style or taste. A lesson only if `rules.md` already has a
     matching preference or the same preference appears in two or more PRs.
4. Show the developer a table: comment (short quote, reviewer, `file:line`),
   class, proposed lesson. Ask which to file.
5. File the kept lessons as feedback issues, as above, with the review comment's
   link as evidence.

Never reply to, resolve, or react to the reviewers' comments.

## `consolidate`: rules owners turn feedback into a rules PR

Only run this for someone listed in `config.json`'s `owners` (compare with
`gh api user -q .login`); otherwise explain who the owners are and stop.

1. List open feedback issues: `gh issue list --label <feedback_label> --state open
   --json number,title,body,comments`.
2. Group issues that propose the same or overlapping changes. Count occurrences.
3. **Conflict check.** For each proposal, compare it with every rule in `rules.md`
   and with `examples.md`. A conflict is any case where following both would put the
   same finding in different categories, or require opposite code. Show each
   conflict side by side and ask the owner which wins.
4. Walk the owner through each group: **Accept** (with edits) / **Reject** (ask for
   the reason, which goes in the issue comment) / **Defer**.
5. For accepted changes, create a branch from the default branch
   (`rules/<label>-<YYYY-MM-DD>`), edit only repo-owned files (`rules.md`,
   `canonical.md`, `surfaces.md`, `examples.md`, `security_patterns.json`, the linter config files named in
   `config.json`'s `checks.items[].config`, and a line in `CHANGELOG.md` under
   "Rules"), commit, and with the
   owner's go-ahead push and open a PR whose body lists each change with
   `Closes #<feedback issue>`. Request review from the other owners.
6. Close rejected issues as not planned with the reason. Leave deferred ones open.

**ID pattern changes** (`target: "security_patterns"`). If the repo has no
`security_patterns.json` yet, copy `assets/security/pii_patterns.json` to it and set
`config.json`'s `security.patterns` to `"security_patterns.json"`. Prefer the narrowest change: a value
to ignore (`ignore_values`) or a column name over loosening an identifier pattern.
Before proposing it, test it: run `scan_branch.py --text` on a scratch file holding
an example of the false alarm (made up, never a real value) and one of a real ID
(also made up), and show the owner that the first no longer matches and the second
still does. Also check it against the security entries in
`evals/labeled_findings.json`: a change that would stop matching a finding the
owners rated Surface is a conflict.

**Code-check changes** (`target: "lint_config"`). Change the tool's own config file
(the `config` of its `checks.items` entry) and the matching **Code checks** rule in
`rules.md` together, in the same commit, so the setting and its reason never drift
apart. The conflict check also covers:

- CI: if a workflow runs the same tool with its own arguments (`mirrors_ci`), the
  change must not make the local check and CI disagree; change both or neither.
- Principles: turning off a rule that enforces a `rules.md` principle (a banned
  import that encodes "one way to connect") is a conflict, shown side by side.
- Scope of impact: run `run_checks.py --only <tool>` across the repo's last few
  merged PRs (as in calibration) and tell the owner how many findings the change
  adds or removes.

Adding a whole new tool (a new `checks.items` entry) is allowed too, if the owner
accepts it: test its command on a real file first and record its install hint.
`checks` and `security.patterns` are the only parts of `config.json` consolidate
changes.

Never edit engine files (`SKILL.md`, `references/`, `assets/`, including
`assets/security/gitleaks_extra.toml`) here. Problems with
the engine itself go to the skill's maintainers: say so and suggest the developer
report them where the `pr-blueprint` skill is published.

## Conflict check (shared by "End of a run" and `consolidate`)

Before proposing any rule, search `rules.md` for rules on the same topic (same
library, same object type, same category language). If one exists, the proposal is
an amendment to that rule ID, not a new rule. If the proposal would reverse a rule,
say so in the issue's "Conflicts" section and quote the rule.

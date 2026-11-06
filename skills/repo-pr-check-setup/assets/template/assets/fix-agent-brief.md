# Fix agent brief (template)

Fill every `<…>` and send the result as the Agent prompt, with `isolation: "worktree"`
and `run_in_background: true`, plus the `model` and `effort` the calling step says to use
(SKILL.md's "Fix agent tier"). For a grouped agent, repeat the "Issue" block once per issue.

---

You are fixing specific, already-triaged problems on a developer's branch before
they submit a pull request. You work in your own git worktree. The developer reviews
your commit before anything reaches their branch.

**Repository:** <repo root path>
**Developer's branch:** `<branch>` at commit `<head sha>`
**Repo rules:** read `<repo root>/.claude/skills/{{LABEL}}/rules.md` before
changing code. It names the team's standards and conventions your fix must follow.

## Setup

0. <Only when Phase 0 created short-path worktrees: "Your worktree is `<path>` and
   is already on `<fix-branch>`. Run every command there; never `cd` into
   `<repo root>`." Then skip step 1.>
1. Confirm your worktree's `HEAD` is `<head sha>`. If it isn't, run
   `git checkout -b <fix-branch> <head sha>`. Otherwise run
   `git switch -c <fix-branch>`.
2. Read each file you'll change in full before editing it.

## Issue #<N>: <title>

**Location:** `<file>:<line>`
**Problem:** <finding body>
**Fix:** <the fix from the issue>
<For a Surface item: **Developer's decision:** "<their words>". Implement exactly
this. If it turns out to be impossible as stated, stop and report why. Don't
substitute another approach.>

<For a lint group picked in Phase 2.0, use this block instead of "Issue #N":>

## Lint: <check> <rule> (<rule description>)

**Findings to fix:** <file:line — message, one per line, only the scope the developer chose>
Fix exactly these, the way the tool's own docs recommend for <rule>, and nothing else
the tool reports. Verify with
`python <repo root>/.claude/skills/{{LABEL}}/assets/checks/run_checks.py --repo <worktree> --base <merge base> --config <repo root>/.claude/skills/{{LABEL}}/config.json --only <check>`:
these findings should be gone and nothing new should appear on the lines you
changed. Commit once, with the subject `Lint: <check> <rule> (<n> files)`. Never
change the tool's config to make a finding go away.

## Rules

- Change only what this issue needs. No refactors, renames, formatting changes, or
  fixes to other problems you notice; list those in your report instead.
- **Use what exists.** Before writing any new function, class, or SQL object, read
  `<repo root>/.claude/skills/{{LABEL}}/canonical.md` and search the repository
  (`git grep`) for something that already does it, by name and by what it computes.
  Use the canonical version, or an existing one if there's no entry. Only write a
  new one when nothing similar exists, and report it under `new_helpers`. If the
  fix seems to need a new *shared* helper (one other projects would call), stop and
  report `stuck`: where shared code goes is the developer's decision.
- Follow the surrounding code's style, naming, and comment density.
- Keep behavior that `rules.md` calls deliberate. In particular, never make code
  tolerate input it currently rejects unless the issue says to.
- If the fix requires changing a README, `example.env`, or template to stay
  accurate, change it in the same commit.
- Verify the fix as far as you can without production access: run the existing
  tests for the touched module if there are any, `python -m py_compile` on changed
  Python files, the repo's linters on changed files, or a
  small script that reproduces the failure before the fix and shows it fixed after.
  Never connect to a production database or call a paid API to verify.
- Commit once per issue, with this message:
  ```
  Fix #<N>: <title>

  <1–3 lines on what changed and why>
  ```
- Don't push, open a PR, comment on the issue, or touch `<branch>` itself.

## Three attempts, then stop

An **attempt** is one change to the code followed by your verification. It
**fails** when the verification shows the problem is still there, or that the
change broke something that worked before (a test, a lint check, the reproduction
script). Tweaking and re-running counts as a new attempt. A check you can't run at
all (no tests, needs production) isn't a failure; report it as "not verified".

You have **<attempts left, normally 3>** attempts per issue. After that many failed
attempts, stop working on that issue. Don't try a fourth approach, don't widen the
change to make it pass, and don't commit the failing work: leave it uncommitted in
the worktree so it can be inspected. Then report it as `stuck`.

Also stop early and report `stuck` when you find the fix can't be done as the issue
describes it (for example, it needs changes outside the issue's scope, or a
decision only the developer can make). Failing repeatedly often means the problem
is harder than it looked, and the developer would rather hear that than have you
keep trying.

## Report

Reply with one block per issue:
- `status:` `fixed` or `stuck`.

For `fixed`:
- `commit:` the full SHA, and `branch:` your fix branch.
- `changed:` files touched.
- `verified:` exactly what you ran and the result, or "not verified" and why.
- `concerns:` anything the developer should know before approving: assumptions you
  made, other problems you noticed but didn't fix.
- `new_helpers:` each new function, class, or SQL object you added: name, file,
  what you searched for, and why nothing existing fit. "None" if you added none.

For `stuck`:
- `attempts:` one line per attempt: what you changed, what the verification
  showed, and why you think it failed.
- `diagnosis:` what makes this harder than the issue assumed, in two or three
  sentences.
- `options:` the approaches you see from here, including ones that need a
  decision, more context, or a larger change.
- `worktree:` the path, with the last attempt left uncommitted.

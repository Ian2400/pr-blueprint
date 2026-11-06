# repo-pr-check-setup

A [Claude Code](https://claude.ai/code) skill that builds a bespoke pre-PR review
skill for *your* repository — one that reviews code the way your team actually
reviews it, not generic best practice.

Run `/repo-pr-check-setup` once per repository. It interviews you about your
standards, calibrates its triage by having you rate real findings from your
recent PRs, then commits a skill to `.claude/skills/<name>/` so every developer
who clones the repo gets `/<name>` with no install of their own.

## Install

Copy/paste into your Claude Code CLI prompt:

```
Install the repo-pr-check-setup plugin from https://github.com/Ian2400/repo-pr-check-setup
```

Or, directly:

```
claude plugin marketplace add Ian2400/repo-pr-check-setup
claude plugin install repo-pr-check-setup@repo-pr-check-setup
```

Then, in any repository you want a pre-PR check for:

```
/repo-pr-check-setup
```

## How the generator and interview work

`/repo-pr-check-setup` is itself a skill, run once per repository by whoever
leads its review standards. It does six things, in order, and can pause
between them across sessions (it keeps its own state, so you can pick up where
you left off):

1. **Repository.** Confirms which repository this check is for (`host/owner/name`)
   and verifies `gh` access to it.
2. **Skill name.** Proposes a label derived from the repo name (for example
   `widgets-pr-check`) for you to confirm or change.
3. **Rules owners.** Asks who approves changes to the review rules, and adds
   them to `CODEOWNERS` for `.claude/skills/<name>/`.
4. **The interview.** Reads your CI config, lint setup, and recent PR history
   first, so its questions are specific to your repo rather than generic. Then
   it asks, topic by topic, skipping anything that doesn't apply:
   - **Principles** — where generic code review gets your team wrong, in your
     own words, each with a reason the skill can reuse to judge cases the rule
     doesn't name.
   - **Risk priorities** — which kinds of change deserve a second look, since
     this decides what waits for your sign-off instead of being fixed outright.
   - **Standards** — what's documented where, and what's a clear bug versus a
     judgment call.
   - **Environments**, and **deploying & reverting changes** — what a change can
     affect beyond its own code, and how to undo it.
   - **One way to do each thing** — which implementation is canonical for
     common needs, so the codebase doesn't grow parallel versions of the same
     logic.
   - **What's noise** — what reviewers flag that you don't want repeated.
   - **Shared code**, **PR types**, and **issue policy** — how strict to be
     about linking work, and which PRs need extra scrutiny or sign-off.
   - **Secrets & PII scan** and **code vulnerability scan** — on/off, and the
     ID formats, email domains, and scan profile/budget for your repo.
   - **Code checks** — which linters CI already runs, so the check reuses them
     instead of inventing a second config.
   - **PR description** — which sections your reviewers actually need.
   - **Agent cost and effort** — whether every fix should run at the same
     (expensive) tier, or scale down for low-risk fixes.

   Each answer is drafted into `rules.md`, `canonical.md`, or `surfaces.md` as
   a rule with an ID, your reasoning, and a source date — you see the draft and
   can revise it before moving on.
5. **Calibration.** Runs the generated check against a handful of your team's
   own recent PRs and has you rate its real findings. This is usually where
   setup pauses — you can rate on your own time, or generate now and come back
   to calibrate later. Disagreements turn into calibrated examples and rule
   amendments, so day one isn't generic guessing.
6. **Generate.** Writes the skill into `.claude/skills/<name>/` and opens a PR
   for your rules owners to review. You can also try it once, uncommitted, on
   a real branch before anything is generated for real.

Re-running `/repo-pr-check-setup` on a repo that already has a generated check
lets you recalibrate, change rules owners, or upgrade the engine — your
`rules.md`, `canonical.md`, `surfaces.md`, `examples.md`, and `config.json`
are never overwritten by an upgrade; only the engine files are.

## What the generated check does

On a developer's branch, before they open a PR:

- **Tracks the work.** Finds or drafts the GitHub issue this PR is for, before
  reviewing anything. How strict that requirement is is a per-repo setting.
- **Scans for secrets and personal data** in every commit on the branch — not
  just the diff — before reading anything, and won't push until each item is
  removed or explained. Values stay masked; a pushed secret must be rotated.
  The ID patterns and flagged email domains (shipped as generic placeholders —
  `example.com`, `example.edu`, `example.gov`) are a per-repo setting the setup
  interview asks about.
- **Scans for code vulnerabilities** (auth bypass, injection, unsafe
  deserialization, SSRF, and the rest) with a vendored copy of
  [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill),
  scoped to the files the branch changes.
- **Runs your team's linters** (ruff, sqlfluff, shellcheck, or whatever CI
  already runs), reports first, and fixes only the rules the developer picks.
- **Reviews the diff** and checks every new function against what the repo
  already has, so it doesn't grow parallel versions of the same thing.
- **Triages by vote.** Three agents categorize each finding (Fix with AI /
  Surface to Developer / Note / Drop) and three score its risk 1-5, independent
  of each other and of you.
- **Fixes the clear-cut problems** with agents, one GitHub issue and one commit
  each — risk 4-5 fixes wait for the developer's sign-off, and fix-agent cost
  scales with risk instead of defaulting every fix to the priciest model.
- **Writes the PR description** in three parts (for reviewers, for engineering,
  for on-call) with a machine-readable Deploying-this and Revert plan, then
  opens a draft PR.
- **Learns.** Developer overrides and reviewer comments (`learn <PR#>`) become
  feedback issues; `consolidate` turns them into a rules PR for your team's
  owners to approve.

Everything it learns about your team lives in files it generates and never
overwrites on an engine upgrade: `rules.md`, `canonical.md`, `surfaces.md`,
`examples.md`, `config.json`. The plugin supplies only the engine.

See [`skills/repo-pr-check-setup/SKILL.md`](skills/repo-pr-check-setup/SKILL.md)
for the full mechanics, and its `CHANGELOG.md` for what each version adds.

## Checking for updates to the vendored vulnerability scan

Both this plugin and a skill it already generated can check whether the
vendored `cloudflare/security-audit-skill` copy is behind upstream:

```
/repo-pr-check-setup check-vendor-updates          # this plugin's own copy
/<your-generated-skill-name> check-vendor-updates  # a generated skill's copy
```

See `VENDORED.md` beside the vendored files for how an update gets applied.

## License

MIT — see [`LICENSE`](LICENSE). The vendored
[cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill)
copy keeps its own MIT license; see `UPSTREAM-LICENSE` beside it.

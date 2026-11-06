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

## What the generated check does

On a developer's branch, before they open a PR:

- **Tracks the work.** Finds or drafts the GitHub issue this PR is for, before
  reviewing anything. How strict that requirement is is a per-repo setting.
- **Scans for secrets and personal data** in every commit on the branch — not
  just the diff — before reading anything, and won't push until each item is
  removed or explained. Values stay masked; a pushed secret must be rotated.
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

## Tune it for your fork

```
claude plugin uninstall repo-pr-check-setup
claude plugin marketplace remove repo-pr-check-setup
claude plugin marketplace add Ian2400/repo-pr-check-setup
claude plugin install repo-pr-check-setup@repo-pr-check-setup
```

The PII scan's defaults (`skills/repo-pr-check-setup/assets/template/assets/security/pii_patterns.json`)
ship tuned for a university (student IDs, a placeholder institutional email
domain); the setup interview asks about this per repo, but you may want to
change the shipped defaults for your own fork.

## License

MIT — see [`LICENSE`](LICENSE). The vendored
[cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill)
copy keeps its own MIT license; see `UPSTREAM-LICENSE` beside it.

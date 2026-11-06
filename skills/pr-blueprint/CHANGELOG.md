# Changelog: pr-blueprint

Claude skills have no built-in version field, so this file and git tags are the
source of truth. Tag releases as `skill/pr-blueprint-vX.Y.Z`. The version
here is also the **engine version** stamped into every generated skill's
`config.json`.

## v1.0.0 — 2026-11-06

Initial public release, carried over from an internal tool built and run against
several real repositories before this release. What it generates:

- **Interview-driven setup.** Reads the repo's CI, lint config, and recent PRs,
  then interviews the team lead about their principles, risk priorities, PR
  types, and where the team's standards are documented, writing it all into a
  repo-owned `rules.md`, `canonical.md`, and `surfaces.md`.
- **Calibration.** Runs the generated check against the lead's own recent PRs
  and has them rate real findings, turning disagreements into `examples.md` and
  rule amendments before the skill ever reviews someone else's PR for real.
- **Secrets & PII scan.** Scans every commit on a branch (not just the diff) for
  secrets, personal identifiers, and committed key or data files, with masked
  reporting and a push gate; a repo can set its own ID patterns.
- **Code vulnerability scan.** Vendors
  [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill)
  for a separate scan of the code itself (auth bypass, injection, unsafe
  deserialization, and the rest), scoped to the branch's changed files.
- **Code checks.** Runs the team's own linters (ruff, sqlfluff, shellcheck, and
  whatever else CI runs), reports first, and fixes only the rules the developer
  picks.
- **Triage by vote.** Three category voters and three risk voters triage every
  finding into Fix with AI / Surface to Developer / Note / Drop, with fixes at
  risk 4-5 waiting for the developer's sign-off.
- **Risk-tiered fix agents.** A repo setting (`config.json`'s `fix_agents`)
  scales each fix agent's model and effort to the finding's risk instead of
  pinning every fix to the most expensive tier.
- **Vendor-update checking.** A stdlib-only script lets both this generator and
  a generated skill check whether the vendored vulnerability-scan copy is
  behind upstream, without a git clone or a `gh` dependency.
- **PR descriptions with deploy and revert plans.** Every generated PR
  description ends with a machine-readable Deploying this and Revert plan
  section for on-call, built from the repo's own change surfaces.
- **Learns from feedback.** `learn <PR#>` reads reviewer comments on a
  submitted PR and proposes rule changes; `consolidate` turns collected
  feedback into one rules PR for the owners to approve.

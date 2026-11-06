# Security policy

## Reporting a vulnerability in this tool

If you find a security issue in `pr-blueprint` itself — the setup skill, the
engine it generates into your repo, or how it integrates the vendored
[cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill)
copy — please report it privately using GitHub's
["Report a vulnerability"](https://github.com/Ian2400/pr-blueprint/security/advisories/new)
feature instead of opening a public issue.

Include what you found, where (file and line if you have it), and a rough
sense of impact. You should get a response within a few days; this is a
one-person project, so please be patient.

## What's out of scope here

- **A false positive or a missed finding from a *generated* check scanning
  someone's code.** That's a bug in triage, not a vulnerability in this tool —
  open a normal issue here, or, if it's about a repo's own custom rules,
  tell that repo's rules owners instead.
- **A vulnerability in the vendored `cloudflare/security-audit-skill` copy
  itself**, as opposed to how this project integrates it. Report that
  upstream, at [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill/security).
  A heads-up here is still welcome so the vendored copy can be refreshed.

## Supported versions

Only the latest commit on `main` is supported. This is a young project
without a long-term support policy yet; see `CHANGELOG.md` in
`skills/pr-blueprint/` for what's shipped.

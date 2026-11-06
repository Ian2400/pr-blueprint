# Vendored copy: cloudflare/security-audit-skill

The files in this directory (everything except this one, `VENDOR.json`, and
`UPSTREAM-LICENSE`) are an unmodified copy of `skills/security-audit/` from
[cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill).
`VENDOR.json` is the machine-readable record of which commit — read it, don't
hand-edit it outside the update process below. License: MIT, in `UPSTREAM-LICENSE`.

This copy ships in every skill `pr-blueprint` generates (Phase 1.0a). It's
vendored, not installed from upstream at run time, so a generated skill works
offline and isn't exposed to an upstream change landing mid-run.

## Checking for updates

Both this generator and a skill it already generated can check whether this copy
is behind upstream, with the script that ships beside it:

```bash
python assets/security/check_vendor_update.py --vendor-file assets/security/security-audit-skill/VENDOR.json
```

Exit code 0 means up to date, 1 means upstream has moved (the JSON output names
how far and lists the commit messages), 2 means the check itself failed (network
or API error — never read that as "up to date").

- **The generator** runs this against its own copy (this directory) to know when
  to re-vendor before the next engine release. See "Upgrade the engine" in
  `SKILL.md` and the generator's own `/pr-blueprint check-vendor-updates`.
- **A generated skill** runs this against its own copy, which may be older than
  the generator's current one (it was vendored at that repo's last generate or
  engine upgrade). See `check-vendor-updates` in the generated skill's own modes.

## Updating this copy

1. `git clone --depth 1 https://github.com/cloudflare/security-audit-skill` somewhere scratch.
2. Diff its `skills/security-audit/` against this directory (excluding this file,
   `VENDOR.json`, and `UPSTREAM-LICENSE`). Review the diff like any other
   dependency bump: upstream's prompts govern what a Phase 1.0a run does.
3. Copy the changed files over, update `UPSTREAM-LICENSE` if it changed, and
   update `VENDOR.json`'s `commit` and `vendored_on`.
4. Note the bump in `CHANGELOG.md` (old commit -> new commit, and anything that
   changed Phase 1.0a's behavior: new attack-class files, a changed
   profile/budget contract, a changed `findings.json` schema).
5. Never hand-edit a file in this directory outside this process — the next
   update will silently discard local changes. A real local tweak belongs in
   `config.json`'s `security.vuln_scan` settings or in `rules.md`, not in the
   vendored prompts.

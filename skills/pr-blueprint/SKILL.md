---
name: pr-blueprint
description: >
  Walks a team lead through creating a bespoke pre-PR review skill for one GitHub
  repository: confirms the repository and the skill's name (e.g.
  widgets-pr-check), sets who owns the review rules (CODEOWNERS), interviews the
  lead about their standards, calibrates triage by having them rate real findings
  from their recent PRs, sets up its built-in scan for secrets and personal data
  and its code checks (ruff, sqlfluff, shellcheck, plus the team's own linters and
  rule preferences),
  then generates the skill into the repo's
  .claude/skills/<name>/ and opens a PR for the owners. Also re-runs on a repo that
  already has one, to recalibrate, change rules owners, or upgrade the engine. Use
  when someone says "set up a PR check for our repo", "create a PR review skill for
  my team", "make our own pr-check", "recalibrate our PR check", "add an owner to
  our PR check rules", "upgrade our pr-check skill", or invokes
  /pr-blueprint. "/pr-blueprint check-vendor-updates" checks whether
  this generator's own vendored cloudflare/security-audit-skill copy is behind
  upstream (see "Checking for vendor updates" below) without running the rest of
  setup. Do NOT use to run a PR check on a branch (that's the
  generated <name>-pr-check skill), or for one-off code review.
---

# PR Blueprint

You help a team lead build a pre-submission PR check that reviews code the way
*their* team reviews it. The output is a skill committed to their repository,
`.claude/skills/<label>/`, that every developer who clones the repo gets
automatically. It finds problems, sorts them into **Fix with AI** / **Surface to
Developer** / **Note to Developer** by this team's standards, fixes the clear-cut
ones with agents, and learns from feedback over time.

Generic code review over-reports: most teams find a large share of its findings
trivial or wrong for their codebase. The interview and the rating step exist to
learn where this team draws the lines between Fix with AI, Surface to Developer,
Note to Developer, and Drop.

## Bundled resources

| Path | Use |
|---|---|
| `references/interview.md` | The interview: topics, question wording, how answers become rules. Read before Step 4. |
| `references/calibration.md` | Picking PRs, running the reviews, the rating page, turning ratings into examples and rules. Read before Step 5. |
| `assets/template/` | The generated skill. Engine files are copied as is (after filling `{{…}}`); repo-owned files are filled from the interview and ratings. |
| `assets/rater/` | The rating page template and `build_rater.py`. |

**Engine vs. repo-owned files** in the generated skill:

| Engine (replaced on upgrade) | Repo-owned (never overwritten) |
|---|---|
| `SKILL.md`, `references/*`, `assets/*` (including `assets/security/` and `assets/checks/`), `evals/trigger_eval.json` | `rules.md`, `canonical.md`, `surfaces.md`, `examples.md`, `config.json`, `CHANGELOG.md`, `evals/labeled_findings.json`, `security_patterns.json` (optional) |

Linter configs (`pyproject.toml`'s `[tool.ruff]`, `.sqlfluff`, `.shellcheckrc`, ...)
live at the repo root, outside the skill, because CI and editors read them too.
Setup and `consolidate` edit them only with the owners' approval; upgrades never
touch them.

The generated skill is self-contained: its security scan (`assets/security/`) carries
copies of the `repo-security-audit` skill's gitleaks rules and ID patterns, so
developers need only gitleaks and Python, not that skill. Refresh those copies here
when the audit's rules change, and they reach every repo on its next engine upgrade.

It also vendors a full copy of
[cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill)
at `assets/security/security-audit-skill/` for its code vulnerability scan (Phase
1.0a). That copy can go stale independently of this generator's own releases —
see "Checking for vendor updates", below.

## Checking for vendor updates

Two copies of `cloudflare/security-audit-skill` exist and can each drift from
upstream on their own schedule:

1. **This generator's own copy**, in `assets/template/assets/security/security-audit-skill/`
   — the one every new or upgraded generated skill gets.
2. **Each generated skill's copy**, vendored at its last generate or engine
   upgrade — may be older than #1 if the repo hasn't upgraded recently.

Both carry a `VENDOR.json` (repo, commit, vendored date) beside the vendored
files, and both ship `assets/security/check_vendor_update.py` to check it:

```bash
python assets/security/check_vendor_update.py --vendor-file assets/security/security-audit-skill/VENDOR.json
```

Exit 0 = up to date, 1 = upstream has moved (prints how far and what changed),
2 = the check itself failed (never read that as "up to date").

- **Maintaining this generator:** run it against #1 periodically (there's no
  schedule enforced — a stale copy only matters the next time someone runs setup
  or an upgrade), or when a lead reports something from topic 11a that doesn't
  match what's vendored. On an update, follow `VENDORED.md`'s steps in that
  directory, then bump `engine_version` here and add an Engine line to this
  skill's own `CHANGELOG.md`, same as any other engine change.
- **A generated skill checks #2** for itself with its own `/{{LABEL}}
  check-vendor-updates` mode (see its `SKILL.md`). That only tells the lead their
  copy is behind *upstream* — getting the fix requires an engine upgrade here
  (Step 1), which re-vendors from #1, so keep #1 current or the upgrade won't help.

## Setup state

Setup spans more than one session (the lead rates findings in between). Keep state in
`$(git rev-parse --git-common-dir)/pr-blueprint/<label>.json` in the target
repo's clone: the answers from each step, the PRs chosen, the review files' location,
the rating page URL, and which step is next. On start, if a state file exists, say
which step you're resuming and continue.

---

## Step 1 — Repository

Ask the lead **which repository** this check is for, as `host/owner/name`
(for example `git.example.com/acme/widgets` or
`github.com/acme/pipelines`). Offer the current directory's `origin` remote as the
first option if there is one, but always confirm: the skill is bound to exactly one
repository.

Then verify:

1. `gh auth status --hostname <host>`; if not logged in, tell them to run
   `gh auth login --hostname <host>` and stop.
2. `gh repo view <host>/<owner>/<name> --json nameWithOwner,defaultBranchRef,viewerPermission`.
   They need at least write permission to open the setup PR.
3. A local clone: the current directory's `origin` must match. If it doesn't, ask
   for the path to a clone (or offer to `gh repo clone` it to a location they
   choose), and work there from now on.
4. **Existing check.** Look for `.claude/skills/*/config.json` with
   `"generator": "pr-blueprint"` on the default branch. If one exists, ask
   what they want:
   - **Recalibrate:** Step 5 only, then update `examples.md` (and rules the ratings
     change) through a rules PR.
   - **Change rules owners:** Step 3 only, then update `CODEOWNERS` and
     `config.json`'s `owners`.
   - **Upgrade the engine:** replace engine files from `assets/template/`, keep
     repo-owned files, bump `engine_version`, add an Engine line to its CHANGELOG,
     and open a PR. Show the engine diff summary first. If the new engine expects a
     repo-owned file the repo doesn't have yet (for example `surfaces.md`), run the
     interview topic that creates it. If it reads a `config.json` key an older
     repo's file lacks (for example `security`, `checks`, or `fix_agents`), run
     that key's interview topic and add just that key; change nothing else in
     those files. A repo with no `fix_agents` key defaults to `{"tiering": "flat",
     "surfaced_tier": {"model": "opus", "effort": "high"}}` (every fix agent at the
     top tier) until the lead answers topic 14.
   - **Start over:** the full flow; the PR replaces the old skill folder.

   Whichever they pick, also run the feedback label check from Step 6.4; repos set
   up before it was required may not have the label.

## Step 2 — Skill name

Propose a label: the repository name, lowercased with everything but letters and
digits removed, plus `-pr-check` (`widgets` → `widgets-pr-check`). Ask the
lead to confirm or type their own. The label:

- must match `^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$`;
- must not already be a folder in the repo's `.claude/skills/`;
- should be distinct across the team's repositories, since developers who work in
  several repos see each one's skill. Warn (don't block) if it is generic, like
  `pr-check`.

Developers will type `/<label>`, so it should read well.

## Step 3 — Rules owners

Ask who decides what the rules are. Explain briefly: owners approve every change to
the rules, through `CODEOWNERS`; they can be one person, several people, or a GitHub
team (`@org/team`), and the list can change later by re-running this step.

- Verify each user with `gh api users/<login> --hostname <host>` (teams with
  `gh api orgs/<org>/teams/<slug> --hostname <host>`).
- Check whether the repo has a `CODEOWNERS` file (`.github/`, root, or `docs/`).
  The new line goes in the existing file, or a new `.github/CODEOWNERS`:
  `/.claude/skills/<label>/ @owner1 @owner2`. In CODEOWNERS the **last** matching
  line wins, so append it after broader patterns.
- CODEOWNERS only *requires* the owners' approval when branch protection on the
  default branch has "Require review from Code Owners" on. Check with
  `gh api repos/<owner>/<name>/branches/<default>/protection --hostname <host>`
  (a 404 or 403 means you can't tell). Tell the lead what you found; never change
  branch protection yourself.
- With exactly one owner and that setting on, tell the lead how their own rules PRs
  (including `consolidate`'s) will merge: GitHub won't let them approve their own
  PR, so it takes an admin bypass or a second owner. A single owner is a fine
  model: the lead proposes rule changes and the team reviews and comments on the
  rules PR before it merges. Just make sure the lead knows which merge path
  they'll use.

## Step 4 — Interview

Read `references/interview.md` and run it. Batch questions; use AskUserQuestion
where answers are choices, chat where they're open. Draft `rules.md` sections as you
go, each rule with an ID, reason, and source "setup interview, <date>". Show the
lead the draft rules before Step 5.

## Step 5 — Calibrate

Read `references/calibration.md` and run it: choose PRs with the lead, review them,
publish the rating page, wait for the ratings (this is where setup usually pauses),
then turn the ratings into `examples.md`, `evals/labeled_findings.json`, and any new
or amended rules the lead confirms.

The lead may choose **rate later**: generate the skill now with
`"calibrated": false` and an empty `examples.md`, and tell them to re-run setup and
pick **Recalibrate** when they have time.

## Step 6 — Generate

**Local trial first?** Ask the lead whether to try the check on a branch before
anything is committed. If yes, do substeps 2 (fill the template) and the linter
config part of it, but write into the **current worktree** instead of a setup
branch, and keep everything out of git:

- write `.claude/skills/<label>/` and any new root configs (`.sqlfluff`, ...) as
  untracked files;
- add each of those paths to `$(git rev-parse --git-common-dir)/info/exclude`, so the
  generated check's clean-tree test (Phase 0) passes and nothing gets committed by
  accident; tell the lead it applies to every worktree of this clone until removed;
- record `"trial": true` and the paths in the setup state.

Then the lead runs `/<label>` on a branch in that worktree (a new session may be
needed for Claude Code to load the new skill). It will file issues and push only
after its own go-ahead questions; for a trial, keep it private by picking **Use an
existing issue** (or saying no issue is needed) when Phase 0 asks about the work
issue, and **Stop here** at the Phase 1 go-ahead. When they're done, delete the trial files and the
`info/exclude` lines, and continue with substep 1 below to generate for real (with
any rule changes the trial taught).

1. Create a branch from the default branch: `setup/<label>`. If the clone's
   working tree is dirty or on another branch, use a separate worktree; on Windows
   with long paths, a sparse checkout of just `.claude/` and `.github/` avoids
   path-length failures.
2. Copy `assets/template/` to `.claude/skills/<label>/` and fill every `{{…}}`:

   | Placeholder | Value |
   |---|---|
   | `{{LABEL}}`, `{{HOST}}`, `{{REPO}}` | Steps 1–2 (`REPO` is `owner/name`) |
   | `{{ENGINE_VERSION}}` | this skill's version, from its `CHANGELOG.md` |
   | `{{DATE}}` | today, `YYYY-MM-DD` |
   | `{{OWNERS_JSON}}`, `{{OWNERS_MD}}` | Step 3, as a JSON array and as `@a, @b` |
   | `{{DEFERRED_LABEL_JSON}}` | Step 4's deferred label as a JSON string, or `null` |
   | `{{CALIBRATED}}` | `true` or `false` |
   | `{{ISSUE_POLICY}}` | Step 4's answer on how strictly to require work issues: `always`, `existing_code` (default), `optional`, or `off` |
   | `{{SECURITY_JSON}}` | Step 4's security answers: `{"enabled": true, "block_push": true, "allow_skip": true, "patterns": null, "vuln_scan": {"enabled": true, "profile": "quick", "budget": 20, "scope": "changed_files"}}`, with `patterns` set to `"security_patterns.json"` when the repo has its own ID formats, and `vuln_scan` from interview topic 11a |
   | `{{CHECKS_JSON}}` | Step 4's code checks: `{"scope": ..., "items": [...]}` (format in `assets/template/references/checks.md`); `{"scope": "changed_files", "items": []}` if the lead wants none |
   | `{{FIX_AGENTS_JSON}}` | Step 4's agent cost answer (interview topic 14): `{"tiering": "risk", "tiers": [...], "surfaced_tier": {...}}` or `{"tiering": "flat", "surfaced_tier": {...}}` |
   | `{{PR_DESCRIPTION_JSON}}` | Step 4's PR description choices: `reviewers`, `engineering`, `required`, `title_convention` (see `assets/template/references/pr-description.md`) |
   | `{{PRINCIPLES}}`, `{{RISK_PRIORITIES}}`, `{{CODE_CHECKS}}`, `{{RULES}}`, `{{REVIEW_FOCUS}}`, `{{DONT_REPORT}}`, `{{ISSUES}}`, `{{PR_GUIDANCE}}` | Step 4–5 drafts; "None yet." for an empty section (for Risk priorities, say the generic scale applies) |
   | `{{SURFACES}}` | Step 4's change surfaces, written into `surfaces.md` |
   | `{{CANONICAL}}`, `{{EXPLORATORY}}` | Step 4's canonical implementations and exploratory directories, written into `canonical.md` |
   | `{{PR_TYPES}}` | Step 4's PR types, or "None." |
   | `{{EXAMPLES}}` | Step 5's table, or "Not calibrated yet. Re-run `pr-blueprint` and choose Recalibrate." |
   | `{{INITIAL_RULES_NOTE}}` | e.g. "initial rules from the setup interview; calibrated on 60 ratings of 6 PRs" |

   Upgrading from a version that had `revert.md`: rename it to `surfaces.md` and
   run the interview topic's Deploy questions for each surface.

   If the lead gave their own ID formats, copy `assets/template/assets/security/pii_patterns.json`
   to `.claude/skills/<label>/security_patterns.json` and edit the copy; never edit
   the engine's file.

   Then check no `{{` remains: `grep -rn "{{" .claude/skills/<label>/`. Validate
   `config.json` with `python -m json.tool`. If security is enabled, run the scan
   once on the setup branch
   (`python .claude/skills/<label>/assets/security/scan_branch.py --repo . --base <default branch> --out <scratch>/security.json`)
   to prove it works on this machine; exit code 2 is a setup problem to fix now.

   **Linter configs.** Apply Step 4's code-check preferences to the tools' own
   config files at the repo root: edit the existing ones (show the lead the diff),
   or create `[tool.ruff]` in `pyproject.toml` (or `ruff.toml`), `.sqlfluff`, and
   `.shellcheckrc` where none exist. Never weaken a rule CI already enforces
   without the lead saying so. Then run
   `python .claude/skills/<label>/assets/checks/run_checks.py --repo . --base <default branch> --config .claude/skills/<label>/config.json`
   once. Every check should report `ran` or `no_files`; fix a `not_run` or `failed`
   now.
3. Add the `CODEOWNERS` line from Step 3, and, if the lead wants rules owners to
   approve linter config changes too, one line per config file (`/pyproject.toml`
   would also cover dependency changes; ask before adding that one).
   **Existing PR template.** If the repo has a PR template (`pull_request_template.md`
   at the root, in `.github/`, or in `docs/`, or a `PULL_REQUEST_TEMPLATE/` folder),
   offer to replace it with `assets/pr-template.md`, filled in. It points people to
   `/<label>` and keeps the same three-part headings for anyone writing a PR by
   hand. Before replacing it, list anything the old template asks for that the new
   process doesn't cover yet, and turn each into a rule, a surface, or a PR type
   with the lead, or confirm it's no longer needed.
4. **Feedback label (required).** The learning loop files every lesson as an issue
   with this label, and `consolidate` finds them by it, so without it nothing the
   team learns reaches the rules. Check with
   `gh label list --repo <owner>/<name> --search pr-check-feedback`. If it's
   missing, ask the lead to create it now, either by you
   (`gh label create pr-check-feedback --repo <owner>/<name> --description
   "Proposed changes to the PR check rules"`) or by them in the repo's Labels page
   if your access can't. Check again afterwards. Don't continue to the setup PR
   until it exists; if the lead truly can't create it yet, record that in the
   state file, list it as an unchecked item in the setup PR body, and remind them
   at the end.
5. Show the lead the file list and `rules.md`, then commit:
   `Add /<label> pre-PR check skill`.
6. With the lead's go-ahead, push and open a **draft** PR. Like every PR the
   generated check opens, it links an issue for the work: find one, or offer to
   draft and file "Set up `/<label>`" with the lead's approval, unless the lead
   chose the `off` policy. The body says what the
   skill does, how developers use it (`/<label>`, `learn`, `consolidate`), who owns
   the rules, the calibration summary, whether the security scan is on and blocks
   pushes, which code checks run (and which CI already runs), and that developers
   need Claude Code, plus gitleaks 8.25+ and Python 3.9+ for the security scan and
   each check's tool (`pip install ruff sqlfluff`, shellcheck from winget or brew).
   Request review from the other owners.

## Step 7 — Try it

Offer a dry run: check out the head of a recent PR that wasn't in the calibration
set as a local branch (`git fetch origin pull/<N>/head:pr-check-try-<N>`), and run
the new skill's Phase 1 only, stopping at the plan summary without filing anything.
Show the lead the plan summary. Disagreements become lessons; with the lead's
go-ahead, fold them into `rules.md` on the setup branch before the PR merges.

---

## Guardrails

- **One repository per skill.** Never generate a skill whose `config.json` names a
  repository other than the clone it's committed to.
- **Ask before anything visible.** Pushing, opening PRs, creating labels, and
  publishing the rating page each need the lead's go-ahead.
- **Never change branch protection or repo settings**, and never change git config
  without asking.
- **Snippets and data.** The rating page and `labeled_findings.json` carry short code
  snippets from the repo. Before publishing or committing them, scan for secrets,
  passwords, tokens, personal identifiers (employee or customer IDs, emails, phone
  numbers), and internal hostnames or IPs; drop or redact any snippet that has one.
  The rating page is private to the lead unless they share it.
- **Show before you ask.** The lead sees only your message text, not tool calls,
  tool results, or files you write. Put every draft (rules, `canonical.md`,
  `surfaces.md`, the setup PR description, issues) in your message in full before
  asking them to approve it.
- **Don't invent standards.** Every rule traces to something the lead said or
  rated. If you think a rule is missing, ask.

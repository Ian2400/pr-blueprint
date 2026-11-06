# Setup interview

Goal: a first draft of `rules.md` that captures what this lead cares about and what
they consider noise, in their words. Keep it to about 15 minutes. Calibration
(Step 5) fixes what the interview misses, so don't try to be exhaustive.

## Before asking anything

Learn the repo so your questions are specific, not generic:

- `README` files at the root and in the main directories; the directory layout.
- Languages and frameworks (file extensions, `requirements*.txt`, `pyproject.toml`,
  `package.json`, `*.sql`).
- CI workflows (`.github/workflows/`), lint configs, test directories.
- How code connects to data: grep for connection libraries, drivers, credential
  files, API clients. Note any in-house library that many files import.
- Labels: `gh label list --limit 100`.
- Recent merged PR titles: `gh pr list --state merged --limit 20 --json title,author`.
- An existing `CONTRIBUTING.md`, style guide, or PR template.

Then ask about what you found, e.g. "Most files connect through `gpg_utils`, but
three use `psycopg2` directly. Is `gpg_utils` the required path?"

## Topics

Go in this order. Skip topics that don't apply to the repo.

### 1. Principles (the most important part)

Ask: **"Where does generic code review get your team wrong?"** Then offer examples to
react to, as a multi-select. Each picked one becomes a principle, in their words:

- Fail loudly on unexpected data: errors on schema changes or empty columns are
  deliberate; never suggest tolerating them.
- One way to connect to each data source or service.
- Docs, templates, and example configs must match the code.
- Production runs as a service account; personal-account quirks don't matter.
- Prefer small, explicit code over abstractions / prefer reuse over duplication.
- Tests required for <kind of change>.

Ask for the reason behind each: the reason goes in the rule, and it's what lets the
skill judge cases the rule doesn't name.

### 2. Risk priorities

Ask: **"Which kinds of change worry you most, even when the change looks small?"**
The check scores every finding's risk from 1 to 5, and fixes at 4 or 5 wait for the
developer's sign-off, so this decides what gets a second look. Offer examples to
rank, as a multi-select:

- Anything that touches data features, model inputs, or targets (cleaning, joins,
  filters, imputation, type casts, deduplication).
- Production tables or outputs other people read.
- Scheduled jobs and loads.
- Credentials, access control, and personal data.
- Shared libraries many projects call.
- Public interfaces (APIs, function signatures, file formats).

For each one picked, ask why and what a 5 looks like there. Write them as a short
ranked list, most important first, each with what earns a 4 and a 5. Record the
lead's reason in their words.

### 3. Standards and where they're documented

For each area the repo has (data connections, environments and deployment, database
DDL and SQL conventions, modeling and analysis, APIs, front end, infrastructure):

- What's the standard? Where is it written down? If it's a README in another repo,
  record how to fetch it fresh (`gh api repos/<o>/<r>/contents/<path> -H "Accept:
  application/vnd.github.raw"`); local clones go stale.
- What violations are clear bugs (**Fix with AI**) vs. need the author's judgment
  (**Surface**)?

### 4. Environments

- Which environments exist (dev / test / prd) and how code chooses one.
- Must non-production runs never touch production objects? (Usually yes → Fix with
  AI.)
- How deployment happens (CI, manual, scheduled jobs) and what that makes
  irrelevant (e.g. file modes under manual deploy).

### 5. Deploying and reverting changes

Every PR gets a **Deploying this** section (every step to put it into each
environment, machine-readable so a CD pipeline can use it later) and a **Revert
plan** for its high-risk changes. Merging and reverting the code are always
covered; ask what *else* a change in this repo can affect. Offer examples as a multi-select, and
let the lead add their own:

- Database objects (functions, tables, views, grants)
- Data already written (loads, backfills, deletes)
- Models and scores (which model version is live, predictions written)
- Scheduled jobs and deployed copies (cron, scripts on servers, manual deploys)
- External services (APIs called, messages or emails sent, files delivered)
- Configuration and infrastructure (env files, secrets locations, cloud resources)

For each one picked, ask these and write them down as a surface in
`surfaces.md`, with a short ID (`database_objects`, `data_written`...):

- **Covers:** which changes touch it (paths, object types, keywords to look for).
- **Deploy:** how a change to it goes out today: who runs what, where, in which
  order across environments, and what failure looks like. If it's done by hand,
  write the hand steps; a pipeline can adopt them later.
- **Previous state:** where the old version lives (the base commit, a backup, a
  history table, a model registry).
- **Restore:** the steps, as concretely as the lead can give them.
- **Verify** and **can't be undone:** how to check a restore, and what is lost for
  good (overwritten data, sent messages).

Also ask how scheduled runs and runtime environments (for example environment
files) are set up, since Deploying this records both.

Only record surfaces the lead confirms. A repo with none still gets a
`surfaces.md` that says so; both plans then cover code only.

### 6. One way to do each thing

Small parallel implementations (a second logging setup, a third correlation helper
with slightly different NULL handling) cost little each and a lot together. Before
asking, find the repo's existing duplication: function names defined in several
directories, and shared libraries many files import. Then show the lead what you
found and ask:

- **Which implementation is canonical** for each common need you found (and any
  they name: connections, logging, configuration, dates and time zones, statistics,
  plotting, model training...). Record need, use, known parallel versions, and
  status. "Not decided yet" is a fine answer: the entry is `undecided`, and the
  check asks which one each time it comes up until the owners pick.
- **Which directories are exploratory** (ad hoc analyses, personal folders,
  research), where duplication doesn't matter much.

Write both into `canonical.md`. If a need already has a rule (like a connection
library), the entry points to that rule.

### 7. What's noise

Ask: **"What do reviewers flag that you don't want to hear about?"** Offer:
style/naming, missing type hints, missing docstrings, hypothetical edge cases,
defensive checks, performance on small data, personal-account behavior. These go in
"Don't report" or become Note-level rules.

### 8. Shared code

Which directories are shared utilities that many projects call? Edge cases there are
usually Surface (labeled as edge cases) rather than Notes. Record the paths.

### 9. PR types

Ask: **"Are there kinds of PR that need more than the usual review?"** For example,
PRs that change a model, migrate a schema, touch billing, or change a public API.
For each one:

- **How to recognize it:** paths, file names, or keywords in the diff.
- **Extra sections** its description needs, and what goes in each (these become
  custom sections in `rules.md`).
- **Sign-offs:** who must approve, and how the check should confirm it: look for
  a recorded approval (an issue comment, a PR review, a ticket), or just ask the
  developer whether they have it. Small, high-trust teams often prefer asking.
- **Risk:** how risky a missing sign-off is (default 3).

Write each as a PR type in `rules.md`. Many repos have none; that's fine.

### 10. Issues

The check settles the issue for each PR's work at the start: it finds one, or
offers to draft and file it. Ask **how strict it should be**, as a single choice:

- **Only when changing existing production code** (recommended default,
  `existing_code`): required when the PR modifies or deletes code that already
  exists; offered but optional for new work.
- **Always** (`always`): every PR links an issue.
- **Offer, never require** (`optional`).
- **Off** (`off`): link one if it's found, never ask.

Then ask how the team's branches name issues (for example
`feature/<project>/<number>-...`), any signals that a PR changes production code
(for example an `update/` branch prefix), which labels a work issue gets, and
whether any kinds of PR are exempt. If the team has a written policy on issues,
check the answer agrees with it.

- Area labels to apply by directory (map paths to existing labels; never invent
  labels).
- The label for deferred "not now" issues, if any (`deferred_label`).
- Long-running tracking issues with checklists the skill should match against.

### 11. Secrets & PII scan

Explain in two sentences: before reviewing, the check scans every commit on the
branch for secrets, personal data and other identifiers, and committed key or
data files, and it won't push until each item is removed or the developer explains
it. Then ask, with AskUserQuestion:

- **Turn it on?** On (Recommended) / Off. Off only with a reason, recorded in the
  setup state.
- **Block the push on unresolved items?** Yes (Recommended) / Warn only
  (`block_push: false`).
- **May developers skip the scan for a small change?** Yes (Recommended:
  `/<label> skip-security`, recorded in the PR) / No, always scan
  (`allow_skip: false`).
- **Which ID formats?** The shipped defaults (Recommended: a generic internal
  ID, SSN, card numbers, dates of birth, a configurable email domain, ID, and
  sensitive-record columns) / the shipped defaults plus more. Either way, ask
  what email domain(s) should be flagged — the shipped pattern is a placeholder
  (`example.com`, `example.edu`, `example.gov`) that does
  nothing until replaced. For more, ask what else this repo's data carries
  (employee or donor IDs, a vendor's account numbers, column names their
  extracts use) in words, write them into a repo-owned `security_patterns.json` (a
  copy of the defaults plus theirs), and show the lead what each one matches.
- Developers need Python 3.9+ and gitleaks 8.25+ for the scan. If this repo's
  developers don't have Python (a front-end or SAS-only team), say so, and offer
  **Off** as a real choice.

Also ask where the repo keeps **fake credentials or synthetic data on purpose** (test
fixtures, sample extracts). Record the paths in `rules.md`'s "Don't report" with the
reason. The check still scans them, but it dismisses what's there after checking it
really is fake.

If the repo already runs gitleaks or secret scanning in CI, note it: the check
catches secrets before they're pushed, CI after.

### 11a. Code vulnerability scan

Explain in two sentences: separately from the scan above, the check can also hunt
for vulnerabilities in the code itself (auth bypass, injection, unsafe
deserialization, SSRF, and the like), using a vendored copy of
[cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill)
that ships with every generated skill — scoped to the files each PR changes, not
the whole repository. Then ask, with AskUserQuestion:

- **Turn it on?** On (Recommended) / Off. It's heavier than the secrets/PII scan —
  it spawns its own reconnaissance, hunting, and verification agents — so a small
  or very cost-conscious team may reasonably say Off. Off only with a reason,
  recorded in the setup state.
- **Profile?** `quick` (Recommended: one hunting wave, bounded, good for most
  PR-sized diffs) / `standard` (the full six-phase workflow, for a team that wants
  deeper coverage and will accept the extra time and cost) / `deep` (for a team
  whose changes are routinely high-stakes).
- **Budget (max agent invocations per run)?** 20 (Recommended for `quick`) / a
  number the lead names. This caps the vendored skill's own cost; if the budget
  can't fund its minimum reconnaissance and verification, it reports an
  incomplete run rather than thinning its evidence bar.

Write the answer into `config.json`'s `security.vuln_scan`
(`{"enabled": true, "profile": "quick", "budget": 20, "scope": "changed_files"}`,
or `{"enabled": false}`), inside `{{SECURITY_JSON}}`. This is a plain repo
setting: changing the profile or budget later is a `config.json` edit, not an
engine upgrade.

**Keeping the vendored copy current.** The copy this setup just vendored
(`assets/security/security-audit-skill/`) is current as of the engine version
being generated; see its `VENDORED.md` for how the lead (or anyone on the repo)
checks it for upstream updates later, with `/{{LABEL}} check-vendor-updates`.

### 12. Code checks

The check runs the team's linters on the files a branch changes, reports first, and
fixes only the rules the developer picks, one small commit each. Setup decides which
tools run and which rules they apply.

**Discover before asking.** Read `.github/workflows/*.yml` (which linters CI runs,
with which versions and arguments), `.pre-commit-config.yaml`, `pyproject.toml`
(`[tool.ruff]`, `[tool.isort]`, `[tool.black]`), `ruff.toml`, `setup.cfg` / `.flake8`,
`.sqlfluff`, `.shellcheckrc`, `.editorconfig`, and which file types the repo has
(`git ls-files` by extension). Show the lead a short table: language, files, what CI
runs today, existing config. The check must agree with CI: reuse the same tools and
config files, and never set up a second, different config for the same tool.

- **Follow reusable workflows.** A job that says
  `uses: <org>/<repo>/.github/workflows/<file>.yml@<ref>` runs its steps in another
  repository. Fetch it
  (`gh api repos/<org>/<repo>/contents/.github/workflows/<file>.yml?ref=<ref> -H "Accept: application/vnd.github.raw"`)
  and read the actual commands, including composite actions it calls the same way.
- **Formatters and type checks count.** If CI runs `ruff format --check`, `pyright`,
  `mypy`, or a formatter, add each as its own check (examples in
  `assets/template/references/checks.md`).
- **Defaults CI writes on the fly.** A step that creates a config when the repo has
  none (for example a `.sqlfluff` with `dialect = greenplum` and excluded rules)
  means the local tool would run without those settings. Propose committing the same
  file at the repo root in the setup PR, so CI and the check read one file; CI's own
  "if the repo has one, it wins" logic keeps working.
- **Gitleaks or secret scanning in CI** is covered by the security scan (topic 11);
  note it, don't add it as a code check.

Then ask, batching with AskUserQuestion where answers are choices:

1. **Defaults.** Ruff for Python, sqlfluff for SQL, shellcheck for shell, for every
   language the repo has. If CI runs another tool for a language (flake8, black,
   pylint), ask whether to mirror that instead of, or alongside, the default.
2. **Python (ruff).** Rule sets to select (for example `E`, `F`, `I`, `B`, `UP`,
   `S` for security, `PD` for pandas, `N` for naming) and ones to ignore; line
   length; target Python version; notebooks too (`extend-include = ["*.ipynb"]`).
3. **Imports.** Sorting style (ruff's `I`: first-party packages, sections, one import
   per line or combined); **banned imports** that encode a principle (ruff `TID251`
   `banned-api`, for example "use `gpg_utils`, not `psycopg2`", "no `pandas.read_sql`
   with string formatting"); relative vs. absolute imports (`TID252`).
4. **SQL (sqlfluff).** Dialect (greenplum, postgres, tsql, oracle, snowflake,
   bigquery; per folder if it differs), templater (raw, jinja, dbt), keyword and
   identifier case, aliasing, trailing commas, rules to exclude, max line length.
5. **Shell (shellcheck).** Shell dialect, minimum severity (`style`, `info`,
   `warning`, `error`), codes to disable, whether to follow sourced files.
6. **"What else does your team use?"** Offer a multi-select with Other: R
   (`lintr`), notebooks (`nbqa` with ruff), YAML (`yamllint`), Markdown
   (`markdownlint`), Dockerfiles (`hadolint`), type checks (`mypy`), tests
   (`pytest`), JavaScript/TypeScript (`eslint`), Terraform (`tflint`), SAS or
   anything else with a command line. For each: the command, the files it applies
   to, how it reports (`sarif`, or `file:line: message` → `lines`), its fixer if
   any, and how to install it. Test the command once on a real file before adding
   it.
7. **Scope.** Default for "elsewhere in files you touched": include it
   (`changed_files`, recommended: touched files get cleaner over time) or only the
   developer's own lines (`changed_lines`). Developers can switch per run.

Write `checks` in `config.json` (format in `assets/template/references/checks.md`),
put the rule switches in the tools' own config files, and record each preference in
`rules.md`'s **Code checks** section with an ID, the tool setting it maps to, and the
lead's reason, for example:

```markdown
- **CHK-3: One way to connect.** Ban `psycopg2` imports outside `gpg_utils/`
  (ruff `TID251` in `pyproject.toml`). *Why:* credentials and environment selection
  live in `gpg_utils`. *Source:* setup interview, 2026-10-29.
```

Ask whether linter config changes should need the rules owners' approval too
(`CODEOWNERS` lines for those files; Step 6).

### 13. PR description

The description has three parts: for reviewers, for engineering, for on call.
Deploying this and the Revert plan are always included. Show the section library
from `assets/template/references/pr-description.md` and ask which sections go in
the reviewers' and engineering parts, and which are **required** (never blank). If the security scan is on, suggest `security`
for the reviewers' part (it's one line when nothing is found); if any code checks
are on, suggest `code_checks`. Ask the title
convention, or infer it from recent titles and confirm. Ask what reviewers most need
from a description: that becomes `{{PR_GUIDANCE}}`.

### 14. Agent cost and effort

Explain in two sentences: fix agents are Claude agents that write the actual code
fix for each Fix-with-AI finding; a pricier model and higher effort find harder
bugs but cost more time and money per fix. Then ask, with AskUserQuestion:

- **Scale cost to risk, or keep it flat?**
  - **Scale to risk** (Recommended, `"tiering": "risk"`): cosmetic/low-risk fixes
    use a cheaper, faster tier; only risk 4-5 fixes (which already wait for the
    developer's sign-off) and anything surfaced to the developer and fixed via
    "Fix now" get the most capable tier. Most runs are cheaper; the riskiest work
    still gets full attention.
  - **Flat** (`"tiering": "flat"`): every fix agent uses the same, most capable
    tier, no matter the risk. Simpler, pricier, the current default before this
    topic existed.
- **If scaling to risk, which tiers?** Offer the default and let the lead adjust
  model names or the risk cutoffs:
  - risk 1-2: cheaper model, medium effort
  - risk 3: cheaper model, high effort
  - risk 4-5 and anything surfaced to the developer: most capable model, high
    effort
  Use whichever two models this session has available, cheaper first (for
  example Sonnet and Opus); ask the lead if they'd rather name specific models.
- **If flat**, which model and effort for every fix agent (default: the most
  capable model, high effort)?

Write the answer into `config.json`'s `fix_agents` (`{{FIX_AGENTS_JSON}}`,
format below) — this is a plain repo setting, not a rule, so re-answering it
later is just an edit to `config.json`, never an engine upgrade:

```json
{"tiering": "risk",
 "tiers": [{"max_risk": 2, "model": "sonnet", "effort": "medium"},
           {"max_risk": 3, "model": "sonnet", "effort": "high"},
           {"max_risk": 5, "model": "opus", "effort": "high"}],
 "surfaced_tier": {"model": "opus", "effort": "high"}}
```

or, for flat:

```json
{"tiering": "flat", "surfaced_tier": {"model": "opus", "effort": "high"}}
```

## Writing the rules

- One rule per decision, with an ID (`<AREA>-<n>`), the category consequences, a
  *Why*, and *Source: setup interview, <date>*. See the format in
  `assets/template/references/learning.md`.
- Use the lead's wording where it's clear; tighten, don't embellish.
- Prefer concrete triggers ("a `psycopg2.connect` outside `gpg_utils`") over
  abstractions ("non-standard connections").
- Don't write rules for things the lead didn't say. Note gaps as questions for
  calibration instead.

Show the full draft and revise until the lead is satisfied.

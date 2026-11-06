# Calibration

Calibration shows the lead real findings from their own repo and records how they'd
categorize each. It catches what the interview can't: the lead's actual line between
Fix with AI, Surface to Developer, Note to Developer, and Drop.

## 1. Choose PRs

- List candidates: `gh pr list --state merged --limit 50 --json number,title,author,additions,deletions,changedFiles,mergedAt`.
- Propose 5–7 PRs: large (by additions and files), recent, and spread across the
  repo's main areas and authors. Include at least one or two of the lead's own PRs:
  they know that code best, and their judgment errors in it are good lessons.
- Ask the lead to confirm or swap PRs. Record the list in the setup state.
- Keep one or two good candidates out of the set for the Step 7 dry run.

## 2. Review each PR

For each PR, launch a subagent (in parallel, `run_in_background`, `model: "opus"`,
`effort: "medium"`), read-only. Give
it the PR number, the draft `rules.md` **only as context about the codebase** (it
must not filter by it; the point is to see what a generic review produces), and these
instructions:

> Review PR #<N> in <repo> as a thorough generic code reviewer. Get the diff with
> `gh pr diff <N>` and the head with
> `git fetch origin pull/<N>/head:refs/review/<N>`; read changed files in full with
> `git show refs/review/<N>:<path>`. Don't check out branches or create worktrees.
> Report the 10 most important real problems (fewer if there aren't 10), ranked.
> For each, return JSON: `file`, `line`, `short_summary` (≤72 chars),
> `summary` (2–3 sentences), `failure_scenario` (concrete input → result), and
> `snippet` (≤10 lines of code at that location). Don't include secrets, passwords,
> tokens, personal identifiers, or internal IPs in any field.

Write each result to `<scratch>/reviews/pr-<N>.json` with `pr`, `title`, `author`,
`url`, and `findings`. If a repo has its own review skill or `/code-review`
available, using it instead of the prompt above is fine; keep the same output shape.

**Security scan of each PR** (if the lead turned it on in the interview). Run it
yourself, not in a subagent, after fetching the PR head:

```
git fetch origin pull/<N>/head:refs/review/<N> <default branch>
python assets/template/assets/security/scan_branch.py --repo <clone> \
  --base $(git merge-base <PR's baseRefOid from gh pr view> refs/review/<N>) --head refs/review/<N> \
  --out <scratch>/reviews/security-<N>.json [--patterns <the lead's security_patterns.json draft>]
```

`build_rater.py` adds these findings to the PR's page, masked. Read only the report
and `--peek`, as the generated check does. A secret that looks real in a merged PR is
a live exposure, not a calibration sample: tell the lead in chat (masked, with
`file:line`) before publishing the page, recommend rotating it, and point them to the
`repo-security-audit` skill for the rest of the repo.

**Code checks over each PR** (if any are on). Lint findings aren't rated one by
one; the lead tunes rules from a noise report instead. For each PR, check its head
out into a scratch worktree, copy in the draft linter configs from the interview,
and run the checks against the PR's merge base:

```
git worktree add <scratch>/wt-<N> refs/review/<N>
python assets/template/assets/checks/run_checks.py --repo <scratch>/wt-<N> \
  --base <merge base as above> --config <draft config.json> --out <scratch>/reviews/checks-<N>.json
git worktree remove --force <scratch>/wt-<N>
```

Add up `groups` across PRs into one table: check, rule, findings on the authors'
changed lines, PRs it appeared in, auto-fixable. Show the lead the top 15 and ask,
per rule: **Keep** / **Ignore** (why?) / **Only on changed lines**. Ignores go into
the tool's config with the reason recorded as a **Code checks** rule in `rules.md`
(*Source: calibration noise report, <date>*). A rule that fires on almost every PR
is usually either noise or a real team habit worth one cleanup PR; ask which.

Then **scan every field** for secrets and personal data (regex for emails, long
digit runs that could be IDs, IPs, `password`, `token`, `key=`); redact or drop
findings that carry any.

## 3. Publish the rating page

```
python assets/rater/build_rater.py --reviews <scratch>/reviews --repo <owner/name> \
  --label <label> --order <PR numbers, lead's own first> --out <scratch>/rater.html
```

Ask the lead before publishing. Publish `<scratch>/rater.html` as an Artifact with
capabilities `{"db": {}, "user": {}}`. Give the lead the link and explain:

- Per finding, the category the check *should* give it, the same four the check
  uses: **Fix with AI / Surface to Developer / Note to Developer / Drop**. For Drop,
  why: **Wrong / Deliberate (team principle) / Not our concern**. A **risk score
  from 1 to 5** (optional for dropped findings): how much damage the problem, or a
  wrong fix for it, could do. Optional reason tags, and a note on *why*, which is
  the most valuable part: notes become rules.
- On dry-run pages (findings with a skill category and risk), each card shows
  whether the lead's category and risk match the skill's.
- Per PR: "What did it miss?" and an overall rating.
- They can stop and come back; ratings save as they go. They can share the link with
  other owners, whose ratings are kept separately.

Save the artifact URL in the setup state. Setup pauses here until the lead says
they're done.

## 4. Read the ratings

Read collections `ratings` (docs `<findingId>~<raterId>`: `category`
(`fix|surface|note|drop`), `drop_reason` (`wrong|principle|scope`), `risk` (1-5),
`tags`, `note`, and `skill_category` / `skill_risk` on dry-run findings) and `prnotes` (`missed`, `overall`) with
ArtifactData. The rating *is* the label; no mapping is needed. Drop reasons feed
different places:

| Drop reason | Use |
|---|---|
| Wrong | Calibration only: the review's claim was false |
| Deliberate (team principle) | Check that `rules.md` has the principle; if not, draft one from the note |
| Not our concern | A "Don't report" candidate |

Risk ratings calibrate the **Risk priorities** section, not the categories. Look for
what the lead scored 4 or 5: which kinds of code (feature engineering, loads,
production tables, credentials, shared libraries) keep coming up? Those become or
confirm Risk priorities, ranked by how often and how high they were scored. A
finding scored high in an area the interview didn't name is a question for the
lead, not a rule yet.

**Security ratings** (`source: "security"`) tune the scan, not the categories: the
check always surfaces what it keeps. A security finding rated Note or Drop is noise
to remove. Its drop reason and note say how: a path holding fake data on purpose
goes into "Don't report"; an ID pattern that matches something else (an account
code, a cost center) becomes a change to `security_patterns.json`; a whole rule
that's wrong for this repo is an engine issue to report. Ratings of Fix with AI mean
"surface it", since security items never go to fix agents.

With several raters, where they disagree, show the lead the disagreements and let
them decide. If a note contradicts the category chosen (e.g. category Drop, but the
note says "the suggested fix is wrong, the real problem is…"), ask the lead which
they meant; the usual answer is Surface, reframed.

Older rating pages used **Useful / Trivial / Wrong / Not our concern** plus an
action. If you read one, map Useful + Block merge → fix, Useful + Mention only → fix
(stating impact), Useful + File an issue → surface, Trivial → note, Wrong → drop
(wrong), Not our concern → drop (scope).

## 5. Distill

1. **`evals/labeled_findings.json`:** every rated finding with `id`, `pr`, `file`,
   `line`, `finding`, `failure_scenario`, `snippet`, `label`, `risk`, `maintainer_note`, plus a
   `rating_scale` header naming the four categories. Re-scan snippets before writing.
2. **`examples.md`:** a table of 20–40 findings that teach the most: every Surface
   and Note, every Dropped, every finding with a note, and enough Fix with AI rows to
   show the range, plus every finding scored 4 or 5. Columns: Finding (summary) |
   Category | Risk | Why (from the note or the rule it illustrates). Summaries
   only; no snippets.
3. **Risk priorities from risk scores.** Draft or amend the ranked Risk priorities
   from the 4s and 5s (see above), each with what earned a 4 and a 5 in the lead's
   ratings and *Source: calibration, PR #N, <date>*. Show them to the lead to accept,
   edit, or reject.
4. **Rules from notes.** Read every note and "what did it miss" answer. Where one
   states a general stance ("we always…", "this matters because…"), or several
   ratings share a pattern, draft a rule or amend an interview rule, with
   *Source: calibration, PR #N, <date>*. Show each to the lead to accept, edit, or
   reject.
5. **Contradictions.** If a rating contradicts an interview rule, show both and ask
   which is right. Either the rule changes or the rating was a mistake; don't keep
   both.
6. **Security noise.** Draft the "Don't report" paths and `security_patterns.json`
   changes the security ratings point to (see above), with *Source: calibration, PR
   #N, <date>*, and show each to the lead. Add the rated security findings to
   `labeled_findings.json` with `"source": "security"` and their masked line as the
   snippet, and the instructive ones to `examples.md`, marked "(security scan)".
7. **The lead's own code.** If ratings show the lead's own PR broke one of their
   stated rules, point it out plainly; it's either a lesson about the rule or a real
   issue to file (ask which).

Include the noise report's decisions (rules kept, ignored, limited to changed lines)
in the summary below.

Write a one-paragraph calibration summary (PRs, number of ratings, category counts,
rules added) for the CHANGELOG and the setup PR body.

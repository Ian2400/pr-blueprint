# PR description

A PR description has three readers, and each gets its own part, always in this
order:

| Part | Reader | Answers |
|---|---|---|
| **For reviewers** | Whoever reviews the PR | What changed, why, what the author decided, how it was tested |
| **For engineering** | Whoever deploys it, by hand now or by CD later | What it touches, and exactly how to deploy it |
| **For on call** | Whoever is handling a problem after merge, or an incident tool | How to undo each risky change |

Don't add material for other readers (history, background for future maintainers):
reviews and incidents are when descriptions get read, and the three parts cover
both. Fill every section from the code first, then ask the developer only for what
the code can't say.

## Which sections

`../config.json` picks the sections for the first two parts:

```json
"pr_description": {
  "reviewers": ["summary", "fixes", "follow_ups", "reviewer_notes", "testing"],
  "engineering": ["data_sources"],
  "required": ["data_sources"],
  "title_convention": "<area>: <what changed>"
}
```

- Use the sections in that order and skip any not listed.
- **Deploying this** always ends the engineering part, and **Revert plan** is always
  the on-call part. Neither is configurable, because tools rely on them.
- A **required** section is never left out or blank: write "None in this change"
  when that is true. `fixes`, `follow_ups`, and `reviewer_notes` are left out when
  empty unless they're required.
- `rules.md` can define **custom sections** (under "PR description") and **PR
  types** that add or require sections when a PR matches them. A section name in
  `config.json` that isn't in the library below is a custom section; `rules.md`
  says what goes in it.

## Layout

```markdown
## For reviewers
### Summary
...
### Testing
...

## For engineering
### Data sources and connections
...
### Deploying this
...

## For on call
### Revert plan
...
```

## Section library

### `summary` (reviewers)
```markdown
### Summary
<2–4 sentences: what the change does and why.>

Closes #<work issue>  (when there is one)
```

### `fixes` (reviewers)
```markdown
### Fixes
- Fixes #123: <issue title>
```

### `follow_ups` (reviewers)
```markdown
### Known follow-ups
- #130: <title> (deferred by the author)
- Related #812: <title> (not addressed here)
```

### `reviewer_notes` (reviewers)
```markdown
### Notes for reviewers
- <Each kept Note to Developer item, one line, with file:line.>
```

### `testing` (reviewers)
```markdown
### Testing
<What was run, on what data, and the result. Say what wasn't tested.>
```

### `code_checks` (reviewers)
```markdown
### Code checks
<Which checks ran on the changed files (ruff, sqlfluff, shellcheck, ...) and the
scope. What was fixed, as `Lint:` commits per rule. What's left on the author's lines
and why ("E501 left: long SQL strings, see CHK-2"). Any check that didn't run.>
```

### `security` (reviewers)
```markdown
### Security scan
<"N commits checked for secrets and personal data: nothing found." Or what was found
and done, as kinds and counts ("1 database password removed before push; 1 extract
removed"), never values, masked lines, or data file paths. Say if a pushed secret
was rotated, if the scan didn't run, if the author skipped it (and their reason),
or if the author pushed past an item and why.>
```

### `data_sources` (engineering)
```markdown
### Data sources and connections
| Source | Kind | How it connects | Read / write | Environments |
|---|---|---|---|---|
| `schema.table` | Database table | <connection library and function> | read | dev, prd |
| <service name> | REST API | `requests`, key from <where> | read | — |
| `container/path` | Blob storage | <client library>, creds via <where> | write | prd only |

<Call out anything new, anything that bypasses the team's standard connection path,
and any write to a production object.>
```

### `api_changes` (engineering)
```markdown
### Interface changes
<Public functions, endpoints, CLI flags, schemas, or config keys added, changed, or
removed, and who calls them. Say whether the change is backward compatible.>
```

### Deploying this (engineering, always last in that part)

See `deploy-plan.md`.

### Revert plan (on call, always)

See `revert-plan.md`.

## Finding the data sources

Search the changed files and the code they call:

- Database connections: the connection library `rules.md` names, plus generic
  drivers (`psycopg2`, `sqlalchemy`, `pyodbc`, JDBC URLs), connection strings, and
  credential files.
- Tables and functions: `FROM`, `JOIN`, `INSERT INTO`, `COPY`, `TRUNCATE`,
  `CREATE OR REPLACE`, plus table names in code strings and SQL files.
- APIs and services: HTTP client base URLs, SDK clients, environment variables named
  `*_URL`, `*_KEY`, `*_ENDPOINT`.
- Files: hard-coded paths, network shares, model artifacts.

For each source, find which environment each configuration path resolves to. If you
can't tell where a credential or key comes from, ask; never guess or show the value.

## Asking the developer

Collect every question the code can't answer (why a choice was made, what's live in
production, when a job should run) and ask them in one batch, not one at a time.
Put their answers in their own words, tightened, under the matching section.

## Title

Follow `title_convention`, at most 72 characters, matching the repo's recent PR
titles (`gh pr list --state merged --limit 10`). If the branch closes an issue the
developer was working from, append `(#N)` if recent titles do.

End the description with any attribution line your environment requires.

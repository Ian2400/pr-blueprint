# Code checks

The team's linters, run on what a branch changes. Which tools run is in
`../config.json` → `checks`; which **rules** they apply is in each tool's own config
file at the repo root (the `config` field of each item), the same file CI and
editors read. `../rules.md`'s **Code checks** section says why the team chose them.

```json
"checks": {
  "scope": "changed_files",
  "items": [
    {"name": "ruff", "files": "*.py", "config": "pyproject.toml", "parser": "ruff",
     "cmd": "ruff check --output-format json {files}",
     "fix": "ruff check --fix --select {rules} {files}", "mirrors_ci": ".github/workflows/lint.yml"},
    {"name": "sqlfluff", "files": "*.sql", "config": ".sqlfluff", "parser": "sqlfluff",
     "cmd": "sqlfluff lint --format json {files}", "fix": "sqlfluff fix --rules {rules} {files}"},
    {"name": "shellcheck", "files": ["*.sh", "*.bash"], "config": ".shellcheckrc", "parser": "shellcheck",
     "cmd": "shellcheck -f json {files}", "fix": "shellcheck -f diff --include={rules} {files}", "fix_mode": "diff"}
  ]
}
```

- `parser`: `ruff`, `sqlfluff`, `shellcheck`, `pyright` (`--outputjson`), `sarif` (any
  tool with SARIF output), or `lines` (`file:line[:col]: message`, with an optional
  `pattern` regex using the groups `file`, `line`, `msg`, and `rule`; leave out `line`
  for whole-file findings). `rule` names the rule when the tool doesn't, and
  `fixable: true` marks every finding fixable (formatters). `ok_exit` lists the exit
  codes that mean "ran" (default `[0, 1]`). `install` is the hint shown when the
  tool is missing.
- Formatters are checks too. A whole-file finding (line 0) counts as the author's:

  ```json
  {"name": "ruff-format", "files": "*.py", "parser": "lines", "pattern": "^Would reformat: (?P<file>.+)$",
   "rule": "format", "fixable": true, "cmd": "ruff format --check {files}", "fix": "ruff format {files}"},
  {"name": "pyright", "files": "*.py", "parser": "pyright", "cmd": "pyright --outputjson {files}",
   "config": "pyrightconfig.json"}
  ```

  `sqlfluff format` has no check mode; `sqlfluff lint` already reports the layout
  rules it would fix.
- `fix` is optional: without it, a group can only be fixed by an agent.
- `enabled: false` turns a check off without losing its settings.

## The report (`checks.json`)

- `checks`: per check, `ran`, `no_files`, `not_run` (tool missing, with an install
  hint) or `failed` (the tool errored, with its last output). Only `ran` means
  checked.
- `findings`: `check`, `rule`, `file`, `line`, `message`, `fixable`, and
  `on_changed_line`, which is true when the branch added or changed that line.
- `groups`: per `check:rule`, counts `changed` (the developer's lines) and
  `elsewhere` (the rest of the files they touched), `fixable`, and `files`.

## Scope

- **changed_lines**: only findings on lines the branch added or changed. Nobody is
  held to code they didn't write.
- **changed_files**: also findings elsewhere in the files they touched, so touched
  files get cleaner over time.

`checks.scope` is the team's default. Ask every run whether to include the
"elsewhere" findings, and show both counts so the choice is informed. A fixer works
on whole files, so with **changed_lines** check the diff it produces: if it also
changes lines outside the developer's own, say so and let them decide.

## Picking and fixing

Report first; fix only what the developer picks. One picked group is one commit:

- **Auto-fixable** (`fixable` > 0): `run_checks.py --fix <check>:<rule>[,<rule>]
  --files <files in the chosen scope>`. It refuses a dirty tree, so commit or reset
  between groups. Show `git diff`, then commit `Lint: <check> <rule> (<n> files)`
  when approved; `git checkout -- .` if not.
- **Not auto-fixable**: one fix agent per group, using the lint block in
  `../assets/fix-agent-brief.md`. Its commit is approved in Phase 3.2 like any fix.
- Ruff's unsafe fixes are never applied. A rule whose fix the tool calls unsafe is
  treated as not auto-fixable.

After the fixes, re-run the checks once and show what's left.

## What becomes a lesson

Lint lessons use `target: "lint_config"` (see `learning.md`):

- the developer says a rule is wrong for the team ("we never wrap SQL keywords",
  "that import order fights our formatter");
- the same rule is left unpicked with a reason on several runs (check the open
  feedback issues before filing a new one);
- a reviewer flags something a tool could have caught (`learn`).

Never change a tool's config on the feature branch to make a finding go away.

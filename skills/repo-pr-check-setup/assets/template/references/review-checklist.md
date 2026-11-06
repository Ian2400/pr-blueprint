# Review checklist

Work through the change with these questions. They are where real problems most often turn
up. `../rules.md` adds this repository's own review focus. Report only what you can tie to specific lines and a
concrete failure.

## Correctness

- Does every new or changed call match the signature of what it calls, including
  functions in other modules and shared utilities?
- Are names defined, keys spelled right, and return values (including `None` on
  error) checked by callers?
- Can every branch actually be reached? Look for filters or flags that make a mode
  such as `--reload` impossible.
- Async code: is every coroutine awaited, and is blocking work kept out of the event
  loop?
- Exceptions: does a re-raise escape a handler that was supposed to send an alert or
  clean up?

## Data pipelines and loads (if the change has any)

- Order of operations: is a tracking or "loaded" row written before a step that can
  still fail? Does a validation check run after the data is already committed?
- Idempotency: does a rerun duplicate rows, or hit a unique constraint that silently
  stops new records?
- Atomicity: are truncate and insert, or delete and insert, in one transaction for
  tables people read?
- Time: are timestamps compared in the same time zone? Are DST transitions handled
  for hourly data?
- Is a connection held open across long external calls?

## Environments and deployment

- Can a dev run read or write any production table, file, blob, or model artifact?
- Do dev and prd resolve to different databases under every configuration path,
  including environment-variable overrides?
- Does a multi-environment run exit non-zero if any environment fails?
- Do shell scripts reference real deployed paths? Are executed scripts executable?
- Are dependencies the code imports listed in the environment or requirements file?

## Data access and security

- Does connection code use the team's standard library as the repo rules describe?
  Are there copies of credential helpers that should call the shared one?
- SQL validators and access filters: what gets through? Unqualified system tables,
  missing dangerous functions, fail-open on a malformed config.
- Are secret files created with restrictive permissions from the start, rather than
  chmod-ed afterwards?
- Are user-provided text and personal identifiers kept out of logs?
- SQL DDL: do grants and owner statements target the right object?

## Domain-specific checks

- Whatever `rules.md`'s **Review focus** lists for this repository (for example
  modeling, front-end, or infrastructure checks). Those come from the rules owners,
  not from this checklist.

## Docs, templates, and consistency

- Do the README, `example.env`, and config templates in the changed directories
  describe what the code now does: same providers, variable names, paths, and steps?
- Is the same logic now implemented twice, in this change or alongside existing
  code? Has a copied fix already been made in one copy but not the other? (The
  duplication check in `SKILL.md` 1.2a does this systematically against
  `canonical.md`.)

## Don't report

- Style, naming, or formatting preferences, unless `rules.md` makes them a rule.
- Anything on `rules.md`'s "Don't report" list, and behavior a principle there
  calls deliberate.

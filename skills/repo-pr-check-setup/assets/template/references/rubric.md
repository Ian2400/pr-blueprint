# Triage rubric

Every verified finding gets exactly one category. This file is the generic part.
This repository's own principles and rules are in `../rules.md`, and real findings
the rules owners categorized are in `../examples.md`. Where they disagree with this
file, they win: a specific rule beats a calibrated example, and a calibrated example
beats this rubric.

## The categories

### Fix with AI

A clear defect where you can name the one correct fix, and nothing outside the code
would change it. Typical cases:

- Logic and runtime errors: undefined names, wrong arguments, un-awaited coroutines,
  conditions that can never be true, return values that are ignored.
- Data-loading correctness: tracking rows written before the step that can fail,
  checks that run after the data is already loaded, non-atomic replace of tables
  people read, constraint violations that silently stop new rows.
- Environment separation: a non-production run that can write to production
  data, files, or artifacts.
- Security gaps in data access: filters that fail open, validators with holes,
  secrets readable by others for any window.
- Docs, templates, and example configs that contradict the code they ship with.
- Copy-paste errors (permissions applied to the wrong object), wrong paths in
  deployment scripts.
- Computation bugs with one right answer, such as using data prepared differently
  from what the code downstream expects.
- Anything `rules.md` lists as Fix with AI.

### Surface to Developer

Real, but the developer must decide. Use it when any of these is true:

- **Data types or precision** are involved. The developer may have a reason that
  test data doesn't show.
- **Several valid fixes exist.** Give your suggested fix and let them choose.
- **Design and duplication:** two implementations of the same thing, a new function
  that repeats an old one, with no `canonical.md` entry deciding which wins. Ask
  which version is canonical. (When `canonical.md` names one, it's Fix with AI.)
- **Shared or general-purpose code**, where you can't see every caller. Surface
  edge cases even when they're rare, and label them as edge cases.
- **A behavior change against the documentation or previous behavior**, even if
  small.
- **Runtime or deployment assumptions** that look odd but might be deliberate.
  Present these as "check with you", not as bugs.
- **It hinges on a fact you can't check** from the repository (`needs_check`).
- **Already tracked in an open issue.** Link the issue and ask whether to fix it in
  this PR.

### Note to Developer

True, but not worth a fix or a decision in this PR:

- Hypothetical edge cases that need an improbable input.
- Defensive hardening against situations the team considers acceptable.
- Small housekeeping the developer should check: a dependency missing from an
  environment file, a stale object to clean up after deployment.

### Dropped

- The claim is wrong after verification.
- The "problem" is deliberate behavior that a principle in `rules.md` protects.
- It's on `rules.md`'s "Don't report" list.

## Risk scores

Risk is scored separately from the category, by three risk voters, and the median
is kept. It answers: if this ships unfixed, or a fix for it is wrong, how much
damage can it do? `../rules.md`'s **Risk priorities** says what this team treats as
high-stakes and overrides this scale.

| Score | Meaning |
|---|---|
| 1 | Cosmetic; no effect on behavior or data |
| 2 | Minor; wrong in rare cases, easy to notice and undo |
| 3 | Moderate; a user or job would hit it, but it's contained and visible |
| 4 | High; silently wrong data or outputs, a broken scheduled job, a security or access gap |
| 5 | Critical; corrupts production data or data people rely on, exposes data, or hits a top Risk priority |

Fix with AI findings at 4 or 5 need the developer's sign-off before an agent fixes
them. Notes at 4 or 5 become Surface. Duplication adds one, and is at least 4 when
the duplicated logic is a Risk priority (`SKILL.md` 1.4).

## Always

- **Say what it costs.** Every finding states its real impact. A real bug in a value
  nothing currently uses is still worth fixing, but the finding must say it has no
  current impact.
- **Reframe instead of dropping** when the reviewer's suggested fix and the original
  code both miss the right behavior: state the right behavior and Surface it.

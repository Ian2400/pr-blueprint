# {{REPO}} canonical implementations

One way to do each common thing. When code needs one of these, it uses the
implementation listed here instead of writing its own. `/{{LABEL}}` checks every
new function a PR adds against this list and the rest of the repository (see
"Duplication check" in `SKILL.md`). Rules owners: {{OWNERS_MD}}. Change it the same
way as `rules.md`: through a rules PR. "Which one is canonical?" answers from
checks become proposals to add here.

Each entry says:

- **Need:** what the code is trying to do, in words a reviewer would search for.
- **Use:** the canonical implementation, where it lives, and how to call it.
- **Not:** known older or parallel versions that shouldn't be used or copied.
- **Status:** `canonical`, or `undecided` when several versions exist and the
  owners haven't picked one (the check then asks which, instead of fixing).

## Entries

{{CANONICAL}}

## Exploratory areas

Code here is exploratory or personal; duplication in it is at most a Note.

{{EXPLORATORY}}

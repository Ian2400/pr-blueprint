# Revert plan

Every PR this skill opens or updates ends with a **Revert plan**, the whole
"For on call" part of the description: for each
high-risk change in the PR, how to undo it. It's written for whoever is on call
when something breaks, and for an incident-investigation tool that reads recent
PRs, so it has a readable part and a parseable part with the same content.

What can need undoing beyond the code is different in every repository, so it
isn't defined here. `../surfaces.md` lists this repository's **revert surfaces**
(for example database objects, data already written, deployed jobs): what each one
covers, how to find its previous state, how to restore it, how to check the
restore worked, and what can't be undone. Read it before writing a plan. The plan
mirrors **Deploying this** (`deploy-plan.md`): for each high-risk deploy step, it
says how to undo it.

## Which changes get an entry

Every change group (Phase 1.4) whose median risk is 4 or 5, whether the developer
or a fix agent wrote it. A fix agent's commit for a finding at risk 4 or 5 is a
change group of its own. Changes at risk 1–3 get no entry.

If there are none, still write the section, with `changes: []`, so a reader knows
the PR was assessed.

## Writing an entry

For each high-risk change group:

1. **Code.** Name the commits that make the change. Always give the merge-level
   step first: "revert this PR's merge commit (`git revert -m 1 <merge sha>`)",
   since commit IDs change if the PR is squash- or rebase-merged.
2. **Each surface in `../surfaces.md` the change touches.** Use that surface's own
   steps, filled in with this change's specifics: object names, the base commit to
   restore from, how to find what this change wrote. Read the code to fill them in;
   ask the developer only what the code can't tell you (for example, which
   version is live in production now).
3. **Irreversible.** Anything that can't be put back as it was: data overwritten or
   deleted, objects dropped without a copy, messages already sent. Say what would
   be lost. An empty list means fully reversible.
4. **Verify.** How to check that the revert worked: a query, a command, a file to
   compare.

Write steps someone can follow under pressure: exact names, paths, and commands,
no "as appropriate". Never put secrets, passwords, or credential contents in the
plan.

## Irreversible changes

When a change group has anything irreversible:

- Raise its risk by one (up to 5) and mark it in the plan summary at the end of
  Phase 1, if you can already tell from the code.
- Before the PR is pushed (Phase 3.5), show the developer each irreversible item
  and ask them to acknowledge it, add a safety step first (for example a backup or
  keeping the old version under another name; any code change goes through the
  normal fix flow), or go back. Record the answer in the plan's `acknowledged_by`.

## Format

The readable part comes first: one short paragraph per change, then the block. The
block is fenced YAML under a fixed marker line, so tools can find it:

````markdown
## For on call
### Revert plan

**R1 (risk 5): model_train excludes all-NULL features.** Revert the merge commit,
then restore `retention.model_train` from the base commit... Not reversible: none.

<!-- revert-plan v1 -->
```yaml
version: 1
pr: 1363
base_sha: 1f8bbb08b
head_sha: 691c8eb20
merge: "git revert -m 1 <merge commit of this PR>"
changes:
  - id: R1
    risk: 5
    what: "model_train excludes all-NULL features"
    files: [src/projects/retention/retention_model_train.sql]
    commits: [a1b2c3d]
    surfaces:
      database_objects:
        - "Restore retention.model_train(text, integer) from 1f8bbb08b:src/projects/retention/retention_model_train.sql"
      models:
        - "Set model_id=4 in run_retention_score_or_update.sh on both hosts"
    irreversible: []
    acknowledged_by: null
    verify:
      - "select count(*) from retention.score_model where model_id >= 5  -- expect 0"
```
````

Rules for the block:

- The marker line is exactly `<!-- revert-plan v1 -->`, right before the fence.
- `surfaces` keys are the surface IDs from `../surfaces.md`. Leave out surfaces a
  change doesn't touch.
- `irreversible` is a list of strings; `acknowledged_by` is the developer's GitHub
  login once they've acknowledged, else `null`.
- Keep the readable part and the block in step. When the PR description is
  updated, rewrite both.

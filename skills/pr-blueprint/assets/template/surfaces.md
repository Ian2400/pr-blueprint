# {{REPO}} change surfaces

What a change in this repository can affect beyond its code, how it's deployed, and
how to undo it. `/{{LABEL}}` uses this to write two sections of every PR
description: **Deploying this** (`references/deploy-plan.md`) and the **Revert
plan** (`references/revert-plan.md`). Rules owners: {{OWNERS_MD}}. Change it the
same way as `rules.md`: through a rules PR.

Each surface has an ID (used as a key in both plans' parseable blocks) and says:

- **Covers:** which changes touch it (paths, object types, keywords).
- **Deploy:** how a change to it goes out, step by step, per environment, and what
  failure looks like.
- **Previous state:** where to find what was there before the change.
- **Restore:** the steps to put it back.
- **Verify:** how to check a deploy or a restore worked.
- **Can't be undone:** what is lost for good, and when.

Merging and reverting the code itself is always part of both plans and isn't
listed here.

{{SURFACES}}

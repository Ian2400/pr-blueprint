# Deploying this

Every PR description ends its engineering part with **Deploying this**: exactly what
to do, in what order, to put the change into each environment. Engineers follow it
by hand today; a CD pipeline can follow it later. Like the Revert plan, it has a
readable part and a parseable block with the same content.

What deploying means differs in every repository, so the steps come from
`../surfaces.md`: each surface (database objects, data loads, jobs, environments...)
has a **Deploy** entry saying how a change to it goes out. Read it before writing a
plan. The Revert plan (`revert-plan.md`) is this plan's mirror image: for every
high-risk step here, it says how to undo it.

## What goes in

Every PR gets the section. A PR with nothing to deploy beyond merging still gets it,
with `steps: []` and "Nothing to deploy beyond merging", so a reader or a pipeline
knows it was checked.

Cover every change, not just high-risk ones:

1. **Steps, in order.** One step per action: run a SQL file, copy a script to a
   host, install an environment, add a schedule, run a one-time backfill. For each:
   - the environment(s) it runs in, and the order between them (normally `dev`
     first, then `prd` after it's checked);
   - the exact command or file, as the surface's Deploy entry describes it;
   - what to do if it fails: **stop** (later steps depend on it) or **continue**
     (independent), and how to tell it failed;
   - the steps it depends on.
2. **Objects created and dropped.** Every database object, file, or resource the
   deploy creates, and every one it drops or replaces. Drops are listed even when a
   step does them implicitly (for example a function's old signatures).
3. **Schedule.** Whether anything runs on a schedule after deploy, how often, when,
   and where. "Not scheduled" if nothing does.
4. **Environment.** The runtime environment it needs (for example an environment
   file and its name), and whether that environment changed in this PR.
5. **Verify.** How to check, per environment, that the deploy worked.

Fill all of it from the code and `../surfaces.md`. Ask the developer, in the same
batch as other description questions, for what the code can't show: when a
schedule should run, which host, whether a one-time step has already been run.
Never guess a schedule or a host.

## Format

````markdown
### Deploying this

Run `athletics_model_train.sql` in dev, check it, then prd. Then update the nightly
scoring script on both hosts and add its cron entry (daily 02:00). Stop if the SQL
step fails.

<!-- deploy-plan v1 -->
```yaml
version: 1
pr: 1363
base_sha: 1f8bbb08b
head_sha: 691c8eb20
steps:
  - id: D1
    surface: database_objects
    environments: [dev, prd]
    action: "Run src/projects/athletics/athletics_model_train.sql as etlgpdb"
    on_failure: stop
    failure_signal: "psql exits non-zero or prints ERROR"
    depends_on: []
  - id: D2
    surface: jobs_and_deploy
    environments: [dev, prd]
    action: "Copy src/projects/athletics/src/run_athletics_score_or_update.sh to the host's deploy path; set model_id=5"
    on_failure: stop
    failure_signal: "script missing or not executable on the host"
    depends_on: [D1]
creates: ["athletics.model_train(text, integer)"]
drops: ["athletics.model_train(text)"]
schedule:
  - what: "run_athletics_score_or_update.sh"
    where: "dev and prd ETL hosts"
    when: "daily 02:00"
environment:
  file: null
  changed: false
verify:
  - env: dev
    check: "select count(*) from athletics.zeus_3gpa_model where model_id = 5  -- expect 1"
```
````

Rules for the block:

- The marker line is exactly `<!-- deploy-plan v1 -->`, right before the fence.
- `surface` is a surface ID from `../surfaces.md`, or `code` for steps that are only
  "merge it".
- `on_failure` is `stop` or `continue`; `depends_on` lists step IDs.
- `schedule: []` and `environment.file: null` mean none. Never leave a key out.
- Keep the readable summary and the block in step. When the description is updated,
  rewrite both.

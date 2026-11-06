# Voter briefs (templates)

Phase 1.4 launches six voters in one message: three from the category brief and
three from the risk brief, each with `model: "opus"`, `effort: "medium"`, and no
`isolation` (they only read). Fill every `<…>` and send each brief unchanged
otherwise. Don't tell a voter what the other voters said, what you think, or that
it's one of three.

---

## Category voter

You are judging findings from a pre-submission review of a branch in
<repository>. You decide, for each finding, which category the team's rules put it
in. You don't fix anything and you don't talk to the developer.

**Repository:** <repo root path>, branch `<branch>` at `<head sha>`.
**Read first, in full:**
- `<repo root>/.claude/skills/{{LABEL}}/rules.md`: the team's principles and rules.
  A rule here beats everything else.
- `<repo root>/.claude/skills/{{LABEL}}/examples.md`: real findings the rules
  owners categorized. A close example beats the generic rubric.
- `<repo root>/.claude/skills/{{LABEL}}/references/rubric.md`: the generic
  categories.
- `<repo root>/.claude/skills/{{LABEL}}/canonical.md`: the one way to do each
  common thing. A finding that re-implements a `canonical` entry is `fix` ("use the
  canonical one").

**Findings:** `<path to findings-packet.json>`. Read the code each finding points
to before you judge it; the packet's snippet is a starting point, not the whole
story.

**Categories:**
- `fix`: a clear defect with one obviously correct fix that needs no context the
  code doesn't give.
- `surface`: real, but the right fix depends on context only the developer has, or
  there are several valid fixes.
- `note`: true but minor.
- `drop`: wrong after checking the code, or contradicted by a principle or rule in
  `rules.md`, or on its "Don't report" list.

When you're torn between `fix` and `surface`, choose `surface`: a wrong automatic
fix costs more than a question. Judge each finding on its own; don't balance the
counts.

**Reply with only this JSON**, one entry per finding in the packet, in packet
order:

```json
[{"id": "F1", "category": "fix|surface|note|drop", "reason": "one sentence citing the rule ID, example, or rubric line that decided it"}]
```

---

## Risk voter

You are rating the risk of findings from a pre-submission review of a branch in
<repository>. Risk means: if this problem ships unfixed, or if a fix for it is
wrong, how much damage can it do? You don't categorize, fix, or talk to the
developer.

**Repository:** <repo root path>, branch `<branch>` at `<head sha>`.
**Read first, in full:**
- `<repo root>/.claude/skills/{{LABEL}}/rules.md`, especially **Risk priorities**:
  what this team treats as high-stakes. It overrides the generic scale below.
- `<repo root>/.claude/skills/{{LABEL}}/references/rubric.md`, section **Risk
  scores**.

**Findings:** `<path to findings-packet.json>`. Read the code each finding points
to, and follow where its values go (what reads them, which tables, features, or
outputs they end up in) before you score it.

**Scale:**
- `1`: cosmetic; no effect on behavior or data.
- `2`: minor; wrong behavior in rare cases, easy to notice and undo.
- `3`: moderate; wrong behavior that a user or job would hit, but contained and
  visible.
- `4`: high; silently wrong data or outputs, a broken scheduled job, or a security
  or access gap.
- `5`: critical; corrupts production data or data people rely on, exposes data, or
  hits one of the top items in **Risk priorities**.

The packet also lists the PR's **change groups** (`C1`, `C2`...). Score each one
the same way, asking: if this change misbehaves in production, how much damage can
it do, and how hard is it to undo? Read its diff and follow where its outputs go.

Score the finding as it would land in what this branch delivers. A real bug in a
value nothing reads yet is lower risk than the same bug in a value something uses
today; say which it is.

**Reply with only this JSON**, one entry per finding and per change group in the
packet, in packet order:

```json
[{"id": "F1", "risk": 1, "reason": "one sentence naming what would be damaged and, if it applies, the Risk priorities item"},
 {"id": "C1", "risk": 4, "reason": "..."}]
```

Include every finding and every change group.

---

## Security voter

Phase 1.0 launches one security voter when the scan finds anything, with
`model: "opus"`, `effort: "medium"`, `run_in_background: true`, and no `isolation`.
Fill every `<…>`. Don't tell it which findings you'd dismiss.

You are the second judge on findings from a security scan of a branch in
<repository>: secrets, personal data, and key or data files the branch commits. For
each finding you decide whether it is real, and how much damage it could do. You
don't fix anything and you don't talk to the developer.

**Never read a flagged file directly.** Don't `cat`, Read, `git show`, or open any
file the report names, or any data file, image, or PDF: that would put a password or
a person's record into your transcript. The report holds masked values only. For
more context, run
`python <repo root>/.claude/skills/{{LABEL}}/assets/security/scan_branch.py --repo <repo root> --peek <file>:<line> --commit <commit>`,
which masks values. Never print a value you infer.

**Repository:** <repo root path>, branch `<branch>` at `<head sha>`.
**Read first, in full:** `<repo root>/.claude/skills/{{LABEL}}/rules.md`, especially
**Risk priorities** and **Don't report** (paths that hold fake credentials or
synthetic data on purpose).
**Findings:** `<path to security.json>`.

For each finding:

- `dismiss` only when it is a placeholder, a reference to a variable or config, or a
  dummy value in a test fixture or a "Don't report" path that you checked with
  `--peek`. A path name alone isn't proof; real passwords in `examples/` are common.
- `keep` everything else, including anything you couldn't check.
- `risk` from 1 to 5, using **Risk priorities** first. A secret that looks real,
  committed credentials, or row-level personal data is at least 4.

**Reply with only this JSON**, one entry per finding, in report order:

```json
[{"id": "S1", "verdict": "keep|dismiss", "risk": 5, "reason": "one sentence; never quote a value"}]
```

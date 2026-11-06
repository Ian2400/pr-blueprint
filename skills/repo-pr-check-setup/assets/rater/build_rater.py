"""Build the calibration rating page from per-PR review files.

Usage:
    python build_rater.py --reviews <dir> --repo <owner/name> --label <skill-label> \
        --order 1363 1347 ... --out <page.html>

Each review file is <dir>/pr-<N>.json:
    {"pr": N, "title": "...", "author": "...", "url": "...", "note": "optional",
     "findings": [{"file", "line", "short_summary", "summary", "failure_scenario",
                   "snippet", "skill_category" and "skill_risk" (optional, dry runs)}]}

If <dir>/security-<N>.json exists (scan_branch.py's report for that PR), its findings and
not-inspected files are added after the review's, marked as security findings. They carry
masked lines only.
"""
import argparse, html, json, pathlib

KIND_TEXT = {
    "secret": ("Secret committed", "A credential in the code or history. Anyone who can read the repo can use it "
               "until it is rotated."),
    "cred_file": ("Key or credential file committed", "A key, .env or credential file is tracked in git."),
    "pii": ("Personal data committed", "Identifiers matching the ID patterns, possibly student records."),
    "data_file": ("Data file committed", "A data file was added; the scan found no identifiers, or couldn't read it."),
}


def security_findings(rep, n):
    out = []
    for f in rep.get("findings", []):
        title, why = KIND_TEXT.get(f["kind"], (f["kind"], ""))
        extra = f" Verdict: {f['verdict']}." if f.get("verdict") else ""
        if f.get("distinct"):
            extra += " Distinct values: " + ", ".join(f"{k} {v}" for k, v in f["distinct"].items()) + "."
        out.append({"id": f"{n}-{f['id']}", "source": "security", "file": f["file"], "line": f["line"] or None,
                    "short_summary": f"{title} ({f['rule']})"[:72], "summary": why + extra,
                    "failure_scenario": "Still in the merged code." if f.get("in_head") else
                    "Removed before merge, but still in the PR's history.",
                    "snippet": f.get("masked") or ""})
    files = [x["file"] for x in rep.get("not_inspected", [])]
    if files:
        out.append({"id": f"{n}-ni", "source": "security", "file": files[0], "line": None,
                    "short_summary": f"{len(files)} file(s) the scan couldn't read",
                    "summary": "Images, notebook image outputs or Git LFS objects. A person would have to look at "
                               "them: " + ", ".join(files[:10]), "failure_scenario": "", "snippet": ""})
    return out

ap = argparse.ArgumentParser()
ap.add_argument("--reviews", required=True)
ap.add_argument("--repo", required=True)
ap.add_argument("--label", required=True)
ap.add_argument("--order", nargs="*", type=int, default=None)
ap.add_argument("--out", required=True)
a = ap.parse_args()

here = pathlib.Path(__file__).parent
reviews = pathlib.Path(a.reviews)
order = a.order or sorted(int(p.stem.split("-")[1]) for p in reviews.glob("pr-*.json"))
prs = []
for n in order:
    p = reviews / f"pr-{n}.json"
    if not p.exists():
        print("missing", p.name)
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    sec = reviews / f"security-{n}.json"
    if sec.exists():
        d.setdefault("findings", []).extend(security_findings(json.loads(sec.read_text(encoding="utf-8")), n))
    for i, f in enumerate(d.get("findings", []), 1):
        f["id"] = f.get("id") or f"{n}-{i}"
        f["category"] = None
    prs.append(d)
    print(n, len(d.get("findings", [])))

subtitle = (f"Findings from a generic code review of recent large PRs in "
            f"<code>{html.escape(a.repo)}</code>. Rate each one; the ratings calibrate "
            f"the <code>/{html.escape(a.label)}</code> skill.")
blob = json.dumps({"prs": prs}, ensure_ascii=False).replace("</", "<\\/")
tpl = (here / "review_rater_template.html").read_text(encoding="utf-8")
out = tpl.replace("__SUBTITLE__", subtitle).replace("/*__DATA__*/", blob)
pathlib.Path(a.out).write_text(out, encoding="utf-8")
print("total", sum(len(p.get("findings", [])) for p in prs), "->", a.out)

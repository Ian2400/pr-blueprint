"""Run this repository's code checks (linters) on the files a branch changes.

Reads the `checks` list from the skill's config.json, runs each check on the changed files it matches,
and writes one report with every finding marked as on a line the branch changed or elsewhere in a file
it touched. Rule choices live in each tool's own config file (pyproject.toml / ruff.toml, .sqlfluff,
.shellcheckrc ...), the same ones CI and editors read; this script never changes them.

Usage:
  python run_checks.py --repo . --base <merge base> --config <skill>/config.json --out <ledger dir>/checks.json
  python run_checks.py --repo . --base <merge base> --config <skill>/config.json \
      --fix ruff:F401,E401 [--files a.py b.py]        # apply one check's own fixer for these rules only

Exit codes: 0 nothing found, 1 findings, 2 a check that had files to check couldn't run (the report says which).
"""

import argparse
import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BATCH = 100  # files per command, under Windows' command-line limit
INSTALL = {
    "ruff": "pip install ruff",
    "sqlfluff": "pip install sqlfluff",
    "shellcheck": "winget install koalaman.shellcheck | brew install shellcheck | apt install shellcheck",
}
LINE_RX = re.compile(r"^(?P<file>[^:\n]+?):(?P<line>\d+)(?::\d+)?:\s*(?P<msg>.*)$")


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    if r.returncode:
        raise SystemExit(
            f"git {' '.join(args[:3])} failed: {r.stderr.decode('utf-8', 'replace').strip()[-300:]}"
        )
    return r.stdout.decode("utf-8", "replace")


def changed(repo, base):
    """({path: set of changed line numbers at HEAD}) for files the branch adds, modifies or renames."""
    files = {
        p: set()
        for p in git(
            repo, "diff", "--name-only", "--diff-filter=AMR", base, "HEAD"
        ).splitlines()
        if p
    }
    path = None
    for line in git(
        repo, "diff", "-U0", "--no-color", "--no-ext-diff", base, "HEAD"
    ).split("\n"):
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@") and path in files:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start, count = int(m.group(1)), int(m.group(2) or 1)
                files[path].update(range(start, start + count))
    return files


def matches(path, globs):
    globs = [globs] if isinstance(globs, str) else globs
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(name, g) for g in globs)


def rel(repo, p):
    p = p.replace("\\", "/")
    root = os.path.abspath(repo).replace("\\", "/").rstrip("/") + "/"
    if p.lower().startswith(root.lower()):
        return p[len(root) :]
    return p[2:] if p.startswith("./") else p


# ---------- parsers: tool output -> [(file, line, rule, message, fixable)] ----------


def parse_ruff(out, repo):
    for f in json.loads(out or "[]"):
        fix = f.get("fix") or {}
        yield (
            rel(repo, f["filename"]),
            (f.get("location") or {}).get("row") or 0,
            f.get("code") or "syntax",
            f.get("message", ""),
            fix.get("applicability") == "safe",
        )


def parse_sqlfluff(out, repo):
    for f in json.loads(out or "[]"):
        for v in f.get("violations", []):
            yield (
                rel(repo, f["filepath"]),
                v.get("start_line_no") or 0,
                v.get("code", ""),
                v.get("description", ""),
                bool(v.get("fixes")),
            )


def parse_shellcheck(out, repo):
    for f in json.loads(out or "[]"):
        yield (
            rel(repo, f["file"]),
            f.get("line") or 0,
            f"SC{f.get('code')}",
            f.get("message", ""),
            bool(f.get("fix")),
        )


def parse_sarif(out, repo):
    for run in json.loads(out or "{}").get("runs", []):
        for r in run.get("results", []):
            loc = (r.get("locations") or [{}])[0].get("physicalLocation") or {}
            yield (
                rel(repo, (loc.get("artifactLocation") or {}).get("uri", "")),
                (loc.get("region") or {}).get("startLine") or 0,
                r.get("ruleId", ""),
                (r.get("message") or {}).get("text", ""),
                False,
            )


def parse_pyright(out, repo):
    for d in json.loads(out or "{}").get("generalDiagnostics", []):
        line = ((d.get("range") or {}).get("start") or {}).get("line")
        yield (
            rel(repo, d.get("file", "")),
            line + 1 if line is not None else 0,
            d.get("rule") or d.get("severity", "error"),
            d.get("message", "").splitlines()[0],
            False,
        )


def parse_lines(out, repo, pattern=None):
    """`file:line[:col]: message` by default; a custom pattern may leave out `line` (a whole-file finding,
    such as a formatter's "Would reformat: x.py") and may name the `rule` group, else the message's first
    code-like word is the rule."""
    rx = re.compile(pattern) if pattern else LINE_RX
    for line in out.splitlines():
        m = rx.match(line.strip())
        if m:
            d = m.groupdict()
            msg = d.get("msg") or line.strip()
            rule = (
                d.get("rule")
                or (re.match(r"\[?([A-Za-z]+[-_]?\d+)\]?", msg) or [None, ""])[1]
            )
            yield (
                rel(repo, d["file"].strip()),
                int(d.get("line") or 0),
                rule,
                msg,
                False,
            )


PARSERS = {
    "ruff": parse_ruff,
    "sqlfluff": parse_sqlfluff,
    "shellcheck": parse_shellcheck,
    "pyright": parse_pyright,
    "sarif": parse_sarif,
    "lines": parse_lines,
}


def split(template):
    """shlex.split that keeps Windows backslash paths ("C:\\Python\\python.exe tools\\x.py") intact."""
    if os.name != "nt":
        return shlex.split(template)
    return [
        t[1:-1] if len(t) > 1 and t[0] == t[-1] and t[0] in "\"'" else t
        for t in shlex.split(template, posix=False)
    ]


def argv(template, files, rules=""):
    """A command template ("ruff check --output-format json {files}") -> argv, with {files} expanded in place."""
    out = []
    for tok in split(template):
        if tok == "{files}":
            out += files
        else:
            out.append(tok.replace("{rules}", rules))
    return out


def run_item(repo, item, files):
    """(status, reason, findings) for one check over its files."""
    cmd0 = split(item["cmd"])[0]
    if not shutil.which(cmd0):
        return (
            "not_run",
            f"{cmd0} is not installed ({item.get('install') or INSTALL.get(item['name'], 'see its docs')})",
            [],
        )
    parser = PARSERS.get(item.get("parser", "lines"))
    if not parser:
        return "failed", f"unknown parser {item.get('parser')}", []
    ok = set(item.get("ok_exit", [0, 1]))
    found = []
    for i in range(0, len(files), BATCH):
        r = subprocess.run(
            argv(item["cmd"], files[i : i + BATCH]), cwd=repo, capture_output=True
        )
        out = r.stdout.decode("utf-8", "replace")
        if r.returncode not in ok:
            return (
                "failed",
                f"exit {r.returncode}: "
                + (r.stderr.decode("utf-8", "replace") or out).strip()[-300:],
                [],
            )
        try:
            found += list(
                parser(out, repo, item["pattern"])
                if parser is parse_lines and item.get("pattern")
                else parser(out, repo)
            )
        except (ValueError, KeyError) as e:
            return "failed", f"couldn't read its output ({e})", []
    return "ran", None, found


def report(a, cfg):
    repo = a.repo
    base = git(repo, "rev-parse", a.base).strip()
    files = changed(repo, base)
    checks, findings = [], []
    for item in cfg.get("items", []):
        if item.get("enabled") is False or (a.only and item["name"] != a.only):
            continue
        mine = sorted(
            p
            for p in files
            if matches(p, item.get("files", "*"))
            and os.path.isfile(os.path.join(repo, p))
        )
        if not mine:
            checks.append({"name": item["name"], "status": "no_files"})
            continue
        status, reason, found = run_item(repo, item, mine)
        checks.append(
            {
                "name": item["name"],
                "status": status,
                "reason": reason,
                "files": len(mine),
            }
        )
        for path, line, rule, msg, fixable in found:
            if path not in files:  # a tool that also reports imported or config files
                continue
            rule = rule or item.get("rule", "")
            findings.append(
                {
                    "check": item["name"],
                    "rule": rule,
                    "file": path,
                    "line": line,
                    "message": msg[:200],
                    "fixable": (fixable or bool(item.get("fixable")))
                    and bool(item.get("fix")),
                    # line 0 is a whole-file finding (a formatter): it's the author's file
                    "on_changed_line": line == 0 or line in files[path],
                }
            )
    findings.sort(
        key=lambda f: (
            not f["on_changed_line"],
            f["check"],
            f["rule"],
            f["file"],
            f["line"],
        )
    )
    groups = {}
    for f in findings:
        g = groups.setdefault(
            f"{f['check']}:{f['rule']}",
            {
                "check": f["check"],
                "rule": f["rule"],
                "changed": 0,
                "elsewhere": 0,
                "fixable": 0,
                "files": set(),
            },
        )
        g["changed" if f["on_changed_line"] else "elsewhere"] += 1
        g["fixable"] += f["fixable"]
        g["files"].add(f["file"])
    for g in groups.values():
        g["files"] = sorted(g["files"])
    rep = {
        "base": base,
        "head": git(repo, "rev-parse", "HEAD").strip(),
        "scope_default": cfg.get("scope", "changed_files"),
        "checks": checks,
        "groups": sorted(
            groups.values(), key=lambda g: (-g["changed"], -g["elsewhere"])
        ),
        "findings": findings,
    }
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
    for c in checks:
        print(
            f"{c['name']:12} {c['status']:8} "
            + (
                f"{c.get('files', 0)} files"
                if c["status"] == "ran"
                else c.get("reason") or ""
            )
        )
    for g in rep["groups"]:
        print(
            f"  {g['check']}:{g['rule']:10} {g['changed']:4} on changed lines, {g['elsewhere']:4} elsewhere"
            + (f", {g['fixable']} auto-fixable" if g["fixable"] else "")
        )
    if any(c["status"] in ("not_run", "failed") for c in checks):
        return 2
    return 1 if findings else 0


def fix(a, cfg):
    """Apply one check's own fixer for the chosen rules; the caller reviews and commits the result."""
    name, _, rules = a.fix.partition(":")
    item = next((i for i in cfg.get("items", []) if i["name"] == name), None)
    if not item or not item.get("fix"):
        raise SystemExit(f"{name} has no fix command in config.json")
    if not rules:
        raise SystemExit("--fix takes CHECK:RULE[,RULE]")
    files = a.files or sorted(
        p for p in changed(a.repo, a.base) if matches(p, item.get("files", "*"))
    )
    before = git(a.repo, "status", "--porcelain")
    if before.strip():
        raise SystemExit(
            "the working tree has uncommitted changes; commit them first so each fix is its own commit"
        )
    rule_arg = ",".join(
        re.sub(r"^SC", "", r) if name == "shellcheck" else r for r in rules.split(",")
    )
    for i in range(0, len(files), BATCH):
        r = subprocess.run(
            argv(item["fix"], files[i : i + BATCH], rule_arg),
            cwd=a.repo,
            capture_output=True,
        )
        if (
            item.get("fix_mode") == "diff" and r.stdout.strip()
        ):  # the tool prints a patch (shellcheck -f diff)
            p = subprocess.run(
                ["git", "-C", a.repo, "apply", "-"], input=r.stdout, capture_output=True
            )
            if (
                p.returncode and b"\r\n" in r.stdout
            ):  # Windows builds print CRLF patches for LF files
                p = subprocess.run(
                    ["git", "-C", a.repo, "apply", "-"],
                    input=r.stdout.replace(b"\r\n", b"\n"),
                    capture_output=True,
                )
            if p.returncode:
                raise SystemExit(
                    "couldn't apply the fix: "
                    + p.stderr.decode("utf-8", "replace").strip()[-300:]
                )
    after = [ln[3:] for ln in git(a.repo, "status", "--porcelain").splitlines()]
    print(json.dumps({"fixed_files": after}))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument(
        "--base", required=True, help="the merge base with the PR's base branch"
    )
    ap.add_argument("--config", required=True, help="the skill's config.json")
    ap.add_argument(
        "--out", help="report path; keep it in the ledger directory, inside .git"
    )
    ap.add_argument("--only", help="run just this check")
    ap.add_argument("--fix", help="CHECK:RULE[,RULE] to auto-fix")
    ap.add_argument("--files", nargs="*", help="limit --fix to these files")
    a = ap.parse_args()
    try:
        cfg = json.load(open(a.config, encoding="utf-8")).get("checks") or {}
        return fix(a, cfg) if a.fix else report(a, cfg)
    except SystemExit as e:
        if isinstance(e.code, str):
            print(f"CHECKS FAILED: {e.code}", file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())

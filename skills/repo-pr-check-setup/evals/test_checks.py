"""Regression test for the generated check's code checks (assets/template/assets/checks/run_checks.py).

Builds a throwaway repo whose base already has lint violations, adds a branch with new ones in Python,
SQL and shell plus a team-specific check, and checks the report: changed lines vs. elsewhere, base-only
files ignored, a missing tool reported as not run, and --fix applying one rule as one change.

Usage: python evals/test_checks.py      (needs git, ruff, sqlfluff and shellcheck on PATH)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "..", "assets", "template", "assets", "checks", "run_checks.py")
TODO_CHECK = (
    "import sys\n"
    "for p in sys.argv[1:]:\n"
    "    for i, line in enumerate(open(p, encoding='utf-8'), 1):\n"
    "        if 'TODO' in line:\n"
    "            print(f'{p}:{i}: TD001 TODO left in code')\n"
)
CHECKS = {"scope": "changed_files", "items": [
    {"name": "ruff", "files": "*.py", "config": "pyproject.toml", "parser": "ruff",
     "cmd": "ruff check --output-format json {files}", "fix": "ruff check --fix --select {rules} {files}"},
    {"name": "sqlfluff", "files": "*.sql", "config": ".sqlfluff", "parser": "sqlfluff",
     "cmd": "sqlfluff lint --format json {files}", "fix": "sqlfluff fix --rules {rules} {files}"},
    {"name": "shellcheck", "files": "*.sh", "config": ".shellcheckrc", "parser": "shellcheck",
     "cmd": "shellcheck -f json {files}", "fix": "shellcheck -f diff --include={rules} {files}", "fix_mode": "diff"},
    {"name": "todo", "files": ["*.py", "*.sql"], "parser": "lines", "cmd": f"{sys.executable} tools/todo_check.py {{files}}"},
    {"name": "ruff-format", "files": "*.py", "parser": "lines", "pattern": r"^Would reformat: (?P<file>.+)$",
     "rule": "format", "fixable": True, "cmd": "ruff format --check {files}", "fix": "ruff format {files}"},
    {"name": "pyright", "files": "*.py", "parser": "pyright", "cmd": "pyright --outputjson {files}"},
]}


def run(cwd, *cmd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"{' '.join(cmd)}: {r.stderr}")
    return r.stdout


def write(repo, files):
    for path, text in files.items():
        full = os.path.join(repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def commit(repo, msg, files):
    write(repo, files)
    run(repo, "git", "add", "-A")
    run(repo, "git", "commit", "-q", "-m", msg)


def checks(repo, base, cfg, *extra):
    r = subprocess.run([sys.executable, RUN, "--repo", repo, "--base", base, "--config", cfg, *extra],
                       capture_output=True, text=True, encoding="utf-8")
    return r


def main():
    tmp = tempfile.mkdtemp(prefix="prcheck_lint_")
    failures = []

    def check(cond, what):
        print(("ok   " if cond else "FAIL ") + what)
        if not cond:
            failures.append(what)
    try:
        repo = os.path.join(tmp, "repo")
        run(tmp, "git", "init", "-q", "-b", "main", repo)
        run(repo, "git", "config", "user.email", "t@example.com")
        run(repo, "git", "config", "user.name", "t")
        cfg = os.path.join(tmp, "config.json")
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump({"checks": CHECKS}, fh)
        commit(repo, "base", {
            "pyproject.toml": '[tool.ruff]\nline-length = 100\n[tool.ruff.lint]\nselect = ["E", "F", "I"]\n',
            ".sqlfluff": "[sqlfluff]\ndialect = postgres\n",
            "tools/todo_check.py": TODO_CHECK,
            "app/a.py": "import os\n\n\ndef f():\n    return 1\n",   # F401 already in base
            "app/untouched.py": "import sys\n",                    # base only: never reported
        })
        base = run(repo, "git", "rev-parse", "HEAD").strip()
        run(repo, "git", "switch", "-q", "-c", "feature/x")
        commit(repo, "branch work", {
            "app/a.py": "import os\nimport json\n\n\ndef f():\n    x = 1; y = 2  # TODO tidy\n    return x + y + zz\n",
            "sql/q.sql": "select a, b from t where x=1\n",
            "scripts/run.sh": "#!/bin/bash\necho $1\n",
        })

        out = os.path.join(tmp, "checks.json")
        r = checks(repo, base, cfg, "--out", out)
        check(r.returncode == 1, f"exit 1 when there are findings (got {r.returncode}: {r.stderr.strip()[-200:]})")
        rep = json.load(open(out, encoding="utf-8"))
        st = {c["name"]: c["status"] for c in rep["checks"]}
        check(st == {"ruff": "ran", "sqlfluff": "ran", "shellcheck": "ran", "todo": "ran", "ruff-format": "ran",
                     "pyright": "ran"}, f"every check ran ({st})")
        fs = rep["findings"]
        check(any(f["check"] == "ruff-format" and f["file"] == "app/a.py" and f["line"] == 0 and f["on_changed_line"]
                  and f["fixable"] for f in fs), "a formatter's whole-file finding is the author's and fixable")
        check(any(f["check"] == "pyright" and f["file"] == "app/a.py" and f["rule"] for f in fs),
              "pyright's JSON is parsed (unknown name on the branch's line)")
        by = lambda chk, rule, path: [f for f in fs if f["check"] == chk and f["rule"] == rule and f["file"] == path]
        new_imp = by("ruff", "F401", "app/a.py")
        check(any(f["line"] == 2 and f["on_changed_line"] for f in new_imp), "new unused import is on a changed line")
        check(any(f["line"] == 1 and not f["on_changed_line"] for f in new_imp), "old unused import is 'elsewhere'")
        check(all(f["fixable"] for f in new_imp), "ruff's safe fix marks F401 fixable")
        check(any(f["rule"] == "E702" and f["on_changed_line"] for f in fs), "finds E702 on the new line")
        check(not any(f["file"] == "app/untouched.py" for f in fs), "ignores files the branch didn't touch")
        check(any(f["check"] == "sqlfluff" and f["file"] == "sql/q.sql" for f in fs), "sqlfluff reports on the new SQL")
        check(any(f["check"] == "shellcheck" and f["rule"] == "SC2086" for f in fs), "shellcheck reports SC2086")
        check(any(f["check"] == "todo" and f["rule"] == "TD001" and f["line"] == 6 for f in fs),
              "a team-specific 'lines' check is parsed")
        check(any(g["check"] == "ruff" and g["rule"] == "F401" and g["changed"] == 1 and g["elsewhere"] == 1
                  for g in rep["groups"]), "groups count changed vs elsewhere per rule")

        f = checks(repo, base, cfg, "--fix", "ruff:F401")
        diff = run(repo, "git", "diff")
        check(f.returncode == 0 and "-import json" in diff and "x = 1; y = 2" in run(repo, "git", "show", ":app/a.py"),
              "--fix ruff:F401 removes the unused imports and nothing else")
        run(repo, "git", "commit", "-qam", "Lint: ruff F401")
        s = checks(repo, base, cfg, "--fix", "shellcheck:SC2086")
        check(s.returncode == 0 and '"$1"' in open(os.path.join(repo, "scripts/run.sh"), encoding="utf-8").read(),
              "--fix shellcheck:SC2086 applies shellcheck's own patch")
        run(repo, "git", "commit", "-qam", "Lint: shellcheck SC2086")
        q = checks(repo, base, cfg, "--fix", "sqlfluff:LT09")
        check(q.returncode == 0 and "select\n" in open(os.path.join(repo, "sql/q.sql"), encoding="utf-8").read().lower(),
              "--fix sqlfluff:LT09 runs sqlfluff's fixer for that rule")
        run(repo, "git", "commit", "-qam", "Lint: sqlfluff LT09")
        after = json.load(open(out, encoding="utf-8")) if checks(repo, base, cfg, "--out", out).returncode in (0, 1) else {}
        check(not any(x["rule"] in ("F401", "SC2086", "LT09") for x in after.get("findings", [])),
              "a re-run after the three fix commits no longer reports those rules")

        write(repo, {"app/a.py": "import os\n"})
        dirty = checks(repo, base, cfg, "--fix", "ruff:F401")
        check(dirty.returncode == 2, "--fix refuses a dirty tree, so each fix stays its own commit")
        run(repo, "git", "checkout", "--", "app/a.py")

        broken = dict(CHECKS, items=CHECKS["items"] + [{"name": "hadolint", "files": "*.py", "parser": "lines",
                                                         "cmd": "not-a-real-linter {files}", "install": "brew install hadolint"}])
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump({"checks": broken}, fh)
        m = checks(repo, base, cfg, "--out", out)
        rep = json.load(open(out, encoding="utf-8"))
        miss = [c for c in rep["checks"] if c["name"] == "hadolint"]
        check(m.returncode == 2 and miss and miss[0]["status"] == "not_run" and "brew install" in miss[0]["reason"],
              "a missing tool is 'not_run' with its install hint, exit 2, never clean")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'all passed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

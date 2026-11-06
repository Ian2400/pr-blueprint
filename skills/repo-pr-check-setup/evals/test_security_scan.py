"""Regression test for the generated check's security scan (assets/template/assets/security/scan_branch.py).

Builds a throwaway repo with a remote, a base branch and a feature branch that plants every kind of
finding, runs the scan on base..HEAD, and checks what it reports and that no planted value reaches its
output. Fake values are assembled at runtime so this file holds none.

Usage: python evals/test_security_scan.py      (needs git and gitleaks on PATH)
"""
import json
import os
import random
import shutil
import string
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.join(HERE, "..", "assets", "template", "assets", "security", "scan_branch.py")
rnd = random.Random(7)
PASSWORD = "Qz" + "".join(rnd.choices(string.ascii_letters + string.digits, k=14)) + "!9"
TOKEN = "ghp_" + "".join(rnd.choices(string.ascii_letters + string.digits, k=36))
NB_PASSWORD = "Nb" + "".join(rnd.choices(string.ascii_letters + string.digits, k=12))
MERGE_PASSWORD = "Mg" + "".join(rnd.choices(string.ascii_letters + string.digits, k=14))
MSG_PASSWORD = "Cm" + "".join(rnd.choices(string.ascii_letters + string.digits, k=12))
SAS_PASSWORD = "Sa" + "".join(rnd.choices(string.ascii_letters + string.digits, k=10))
PUIDS = ["0" + "".join(rnd.choices(string.digits, k=9)) for _ in range(30)]
PLANTED = [PASSWORD, TOKEN, NB_PASSWORD, MERGE_PASSWORD, MSG_PASSWORD, SAS_PASSWORD] + PUIDS
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")
LFS = "version https://git-lfs.github.com/spec/v1\noid sha256:" + "ab" * 32 + "\nsize 123456\n"


def run(cwd, *cmd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"{' '.join(cmd)}: {r.stderr}")
    return r.stdout


def commit(repo, msg, files=None, remove=()):
    for path, text in (files or {}).items():
        full = os.path.join(repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(text if isinstance(text, bytes) else text.encode("utf-8"))
    for path in remove:
        os.remove(os.path.join(repo, path))
    run(repo, "git", "add", "-A")
    run(repo, "git", "commit", "-q", "--allow-empty", "-m", msg)


def main():
    tmp = tempfile.mkdtemp(prefix="prcheck_test_")
    failures = []

    def check(cond, what):
        print(("ok   " if cond else "FAIL ") + what)
        if not cond:
            failures.append(what)
    try:
        remote, repo = os.path.join(tmp, "remote.git"), os.path.join(tmp, "repo")
        run(tmp, "git", "init", "-q", "--bare", remote)
        run(tmp, "git", "init", "-q", "-b", "main", repo)
        run(repo, "git", "config", "user.email", "t@example.com")
        run(repo, "git", "config", "user.name", "t")
        run(repo, "git", "remote", "add", "origin", remote)
        commit(repo, "base", {"app/main.py": "print('hi')\n", "README.md": "# demo\n"})
        run(repo, "git", "push", "-q", "origin", "main")
        base = run(repo, "git", "rev-parse", "HEAD").strip()

        run(repo, "git", "switch", "-q", "-c", "feature/x")
        commit(repo, "add db config", {"app/db.py": f'DB_PASSWORD = "{PASSWORD}"\nHOST = "db"\n'})
        commit(repo, "remove password again", {"app/db.py": 'import os\nDB_PASSWORD = os.environ["DB_PASSWORD"]\n'})
        run(repo, "git", "push", "-q", "origin", "feature/x")  # the password commit is now on the server
        rows = "\n".join(f"{p},Student {i},3.{i % 10}" for i, p in enumerate(PUIDS))
        commit(repo, "add extract", {"data/students.csv": "puid,name,gpa\n" + rows + "\n"})
        commit(repo, "add env", {".env": f"GITHUB_TOKEN={TOKEN}\n"})
        commit(repo, "example config", {"app/settings.example.py": 'PASSWORD = "your-password-here"\n'})
        nb = {"cells": [{"cell_type": "code", "source": [f'conn = connect(password="{NB_PASSWORD}")\n'],
                         "outputs": [{"output_type": "display_data", "data": {"image/png": "iVBORw0KGgo="}}]}],
              "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
        commit(repo, "notebook", {"analysis/explore.ipynb": json.dumps(nb)})
        commit(repo, "screenshot and lfs extract", {"docs/query_result.png": PNG, "data/big_extract.csv": LFS})
        commit(repo, "sas load", {"etl/load.sas": f"libname gp greenplm server=db user=me pw={SAS_PASSWORD} schema=s;\n"
                                                    "libname ok greenplm server=db user=me pw=&dbpw schema=s;\n"})
        commit(repo, f"connect with user etl password={MSG_PASSWORD} for now")

        # a conflict whose resolution adds a password neither side had
        run(repo, "git", "switch", "-q", "main")
        commit(repo, "main: change setting", {"app/settings.py": "TIMEOUT = 10\n"})
        run(repo, "git", "push", "-q", "origin", "main")
        run(repo, "git", "switch", "-q", "feature/x")
        commit(repo, "branch: change setting", {"app/settings.py": "TIMEOUT = 30\n"})
        subprocess.run(["git", "merge", "-q", "main"], cwd=repo, capture_output=True)  # conflicts
        with open(os.path.join(repo, "app/settings.py"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f'TIMEOUT = 30\nDB_PASSWORD = "{MERGE_PASSWORD}"\n')
        run(repo, "git", "add", "-A")
        run(repo, "git", "commit", "-q", "--no-edit")

        out = os.path.join(tmp, "ledger", "security.json")
        base = run(repo, "git", "merge-base", "main", "HEAD").strip()  # as the skill passes it
        r = subprocess.run([sys.executable, SCAN, "--repo", repo, "--base", base, "--out", out],
                           capture_output=True, text=True, encoding="utf-8")
        check(r.returncode == 1, f"exit code 1 when findings exist (got {r.returncode}: {r.stderr.strip()[-200:]})")
        rep = json.load(open(out, encoding="utf-8"))
        fs = rep["findings"]
        dump = open(out, encoding="utf-8").read() + r.stdout + r.stderr

        check(rep["commits_scanned"] == 10, "scans every branch commit, none from base or main")
        check(rep["unpushed_commits"] == 9, "counts commits not on the remote (8 and the merge)")
        pw = [f for f in fs if f["kind"] == "secret" and f["file"] == "app/db.py"]
        check(len(pw) == 1 and pw[0]["verdict"] == "looks real" and pw[0]["severity"] == "critical",
              "finds a password that is deleted again later in the branch")
        check(pw and pw[0]["pushed"] and not pw[0]["in_head"], "marks it pushed and gone from HEAD")
        check(any(f["file"] == ".env" and f["kind"] == "cred_file" for f in fs), "flags a tracked .env file")
        check(any(f["file"] == ".env" and f["kind"] == "secret" and not f["pushed"] for f in fs),
              "finds the token in .env and marks it unpushed")
        pii = [f for f in fs if f["kind"] == "pii" and f["file"] == "data/students.csv"]
        check(len(pii) == 1 and pii[0]["severity"] == "high" and pii[0]["distinct"].get("puid") == 30,
              "flags the student extract as high with 30 distinct PUIDs")
        check(any(f["file"] == "analysis/explore.ipynb" and f["kind"] == "secret" for f in fs),
              "finds a password typed into a notebook")
        check(not any(f["file"] == "app/settings.example.py" and f["severity"] != "low" for f in fs),
              "doesn't raise a placeholder in an example file above low")
        check(not any(f["file"] in ("app/main.py", "README.md") for f in fs), "ignores files only the base touched")
        ni = {n["file"]: n["reason"] for n in rep["not_inspected"]}
        check("image" in ni.get("docs/query_result.png", ""), "lists an added image for a person to check")
        check("image outputs" in ni.get("analysis/explore.ipynb", ""), "lists a notebook's image outputs")
        check("LFS" in ni.get("data/big_extract.csv", "")
              and any(f["file"] == "data/big_extract.csv" and f["kind"] == "data_file" for f in fs)
              and not any(f["file"] == "data/big_extract.csv" and f["kind"] == "pii" for f in fs),
              "marks a Git LFS pointer not inspected instead of clean")
        sas = [f for f in fs if f["file"] == "etl/load.sas"]
        check(len(sas) == 1 and sas[0]["line"] == 1 and sas[0]["severity"] == "critical",
              "finds an unquoted SAS pw= and skips a macro reference")
        check(any(f["file"] == "(commit message)" and f["kind"] == "secret" for f in fs),
              "finds a password in a commit message")
        mg = [f for f in fs if f["file"] == "app/settings.py" and f["kind"] == "secret"]
        check(len(mg) == 1 and mg[0]["in_head"] and mg[0]["severity"] == "critical",
              "finds a password added while resolving a merge conflict")
        check(not any(f["file"] == "app/settings.py" and f["commit"] and f["kind"] != "secret" for f in fs),
              "doesn't flag what the merge brought in from main")
        leaked = [v[:4] for v in PLANTED if v in dump]
        check(not leaked, "no planted value appears in the report or output" + (f" (leaked: {leaked})" if leaked else ""))

        p = subprocess.run([sys.executable, SCAN, "--repo", repo, "--peek", "data/students.csv:3"],
                           capture_output=True, text=True, encoding="utf-8")
        check(p.returncode == 0 and not any(v in p.stdout for v in PLANTED), "--peek shows the extract masked")

        body = os.path.join(tmp, "pr_body.md")
        with open(body, "w", encoding="utf-8") as fh:
            fh.write("## Summary\nLoads the extract. Affected students: " + ", ".join(PUIDS[:12]) + "\n")
        t = subprocess.run([sys.executable, SCAN, "--text", body], capture_output=True, text=True, encoding="utf-8")
        check(t.returncode == 1 and "pii" in t.stdout and not any(v in t.stdout for v in PLANTED),
              "--text flags PUIDs pasted into a PR description, masked")

        clean = subprocess.run([sys.executable, SCAN, "--repo", repo, "--base", "HEAD", "--out",
                                os.path.join(tmp, "clean.json")], capture_output=True, text=True)
        check(clean.returncode == 0, "exit code 0 for an empty range")
        bad = subprocess.run([sys.executable, SCAN, "--repo", repo, "--base", "nope", "--out",
                              os.path.join(tmp, "bad.json")], capture_output=True, text=True)
        check(bad.returncode == 2 and "SCAN FAILED" in bad.stderr, "exit code 2, never clean, when it can't run")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'all passed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

"""Check whether a vendored copy of an upstream GitHub skill is behind.

Stdlib only (same philosophy as scan_branch.py): no git clone, no `gh` dependency,
just the public GitHub REST API over HTTPS. Safe to run against any public repo
without auth (rate-limited to 60 calls/hour, which is fine for an occasional
manual or throttled check).

Usage:
  python check_vendor_update.py --vendor-file <path to VENDOR.json>
  python check_vendor_update.py --repo <owner/name> --vendored <commit sha>

VENDOR.json format (lives beside the vendored files it describes):
  {"repo": "cloudflare/security-audit-skill", "commit": "<sha>", "vendored_on": "YYYY-MM-DD"}

Exit codes: 0 up to date, 1 an update is available, 2 the check couldn't run
(network or API error — never treat this as "up to date").
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "repo-pr-check-setup-vendor-check",
}


def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def check(repo, vendored):
    latest = get(f"{API}/repos/{repo}/commits?per_page=1")[0]
    latest_sha = latest["sha"]
    if latest_sha == vendored:
        return {"up_to_date": True, "repo": repo, "vendored": vendored, "latest": latest_sha}
    cmp = get(f"{API}/repos/{repo}/compare/{vendored}...{latest_sha}")
    return {
        "up_to_date": False,
        "repo": repo,
        "vendored": vendored,
        "latest": latest_sha,
        "latest_date": latest["commit"]["committer"]["date"],
        "ahead_by": cmp.get("ahead_by"),
        "commits": [c["commit"]["message"].splitlines()[0] for c in cmp.get("commits", [])][-10:],
        "compare_url": f"https://github.com/{repo}/compare/{vendored[:12]}...{latest_sha[:12]}",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor-file", help="path to a VENDOR.json (repo + commit)")
    ap.add_argument("--repo", help="owner/name on github.com, instead of --vendor-file")
    ap.add_argument("--vendored", help="the vendored commit sha, instead of --vendor-file")
    a = ap.parse_args()
    if a.vendor_file:
        v = json.load(open(a.vendor_file, encoding="utf-8"))
        repo, vendored = v["repo"], v["commit"]
    elif a.repo and a.vendored:
        repo, vendored = a.repo, a.vendored
    else:
        raise SystemExit("--vendor-file, or --repo and --vendored, are required")
    try:
        result = check(repo, vendored)
    except urllib.error.HTTPError as e:
        print(f"CHECK FAILED: HTTP {e.code} from GitHub API ({e.reason})", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"CHECK FAILED: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=1))
    return 0 if result["up_to_date"] else 1


if __name__ == "__main__":
    sys.exit(main())

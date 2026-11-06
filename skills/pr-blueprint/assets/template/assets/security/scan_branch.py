"""Security scan of one branch's own commits: secrets, personal data / PII, and committed key or data files.

Scans every commit in BASE..HEAD, not only the final diff: a password added in one commit and deleted in
the next still ships in the branch's history. Also scans what merge commits add while resolving conflicts,
and the commit messages. Images and Git LFS objects can't be read and are listed for a person to check.
Writes a masked report; no raw secret or identifier is ever written to disk or stdout.

The rules, ID patterns and masking come from the repo-security-audit skill (gitleaks_extra.toml and
pii_patterns.json are copies of its files; the masking and PII code below is trimmed from its scan_repo.py).

Usage:
  python scan_branch.py --repo . --base <base sha> [--head HEAD] --out <ledger dir>/security.json
  python scan_branch.py --repo . --peek FILE:LINE [--commit SHA] [--context 3]    # masked view of a flagged line
  python scan_branch.py --text <draft PR body file>                                # secrets / IDs in a text file

Exit codes: 0 nothing found, 1 findings, 2 the scan could not run (never treat 2 as clean).
"""

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SALT = os.urandom(
    16
)  # discarded at exit: fingerprints group equal secrets but can't be reversed
MAX_BYTES = 50 << 20

TABULAR = {"csv", "tsv", "txt", "dat", "xlsx", "xlsm"}
OPENABLE = {"xlsx", "xlsm", "docx", "pptx", "pdf", "ipynb"}
DATA_EXT = {
    "csv",
    "tsv",
    "xlsx",
    "xlsm",
    "xls",
    "xlsb",
    "dat",
    "jsonl",
    "parquet",
    "feather",
    "dta",
    "sas7bdat",
    "sav",
    "rds",
    "rdata",
    "rda",
    "sqlite",
    "db",
    "mdb",
    "accdb",
    "pkl",
    "pickle",
    "npy",
    "npz",
    "h5",
    "hdf5",
    "zip",
    "7z",
    "tar",
    "tgz",
    "gz",
    "bz2",
    "xz",
    "rar",
    "bak",
    "dump",
    "docx",
    "pptx",
    "pdf",
    "doc",
    "ppt",
    "ods",
    "odt",
    "odp",
    "rtf",
    "msg",
}
TEXT_EXT = {
    "sql",
    "py",
    "sh",
    "md",
    "txt",
    "yml",
    "yaml",
    "json",
    "jsonl",
    "ini",
    "cfg",
    "conf",
    "toml",
    "r",
    "jinja2",
    "html",
    "js",
    "ts",
    "xml",
    "csv",
    "tsv",
    "log",
    "env",
    "rst",
    "ps1",
    "bat",
    "sas",
    "do",
    "sps",
    "rmd",
    "qmd",
    "hql",
    "ddl",
    "scala",
    "java",
    "cs",
    "properties",
    "dat",
}
IMAGE_EXT = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "bmp",
    "tif",
    "tiff",
    "webp",
    "emf",
    "wmf",
    "svg",
    "heic",
}
LFS_POINTER = b"version https://git-lfs.github.com/spec/v1"
VENDORED = re.compile(
    r"(^|/)(venv|\.venv|env/lib|site-packages|dist-packages|node_modules|_build|"
    r"vendor|bower_components)/",
    re.I,
)
KEYFILE = re.compile(
    r"(^|/)(id_rsa|id_ed25519|id_ecdsa|id_dsa|\.pgpass|\.netrc|\.git-credentials|\.pypirc|\.npmrc|"
    r"\.htpasswd|\.my\.cnf|odbc\.ini|\.Renviron|kubeconfig|cwallet\.sso|ewallet\.p12|"
    r"local\.settings\.json)$|(^|/)(\.aws/credentials|\.docker/config\.json|\.kube/config)$|"
    r"\.(pem|key|p12|pfx|jks|asc|cred|creds|ppk|keytab|kdbx|tfstate)$|"
    r"(^|/)[^/]*cred[^/]*\.(txt|json|ini)$|(^|/)[^/]*(service[-_]?account|client_secret)[^/]*\.json$",
    re.I,
)
ENVFILE = re.compile(r"(^|/)\.env(\.[\w-]+)?$", re.I)
ENV_OK = re.compile(r"example|template|sample|dist", re.I)
ENCFILE = re.compile(r"\.(gpg|pgp)$", re.I)
DOC_SECRET = re.compile(
    r"(?i)(?:(?:\b(?:[\w-]*_)?(?:password|passwd|pwd|passphrase)|\b(?:api[_ ]?key|secret|token))\b"
    r"\s*[:=]\s*|[?&;]pass(?:word)?=)"
    r"[\"']?(?!<|\{|\$|x{3}|your|example|enter|\*{3})([^\s\"'&;,]{6,})"
)
URI_SECRET = re.compile(
    r"(?i)\b[a-z][a-z0-9+.-]{1,15}://[^\s:/@'\"]{1,64}:(?!<|\{|\$|\*{3}|password@)([^\s@'\"/]{3,128})@[\w.-]+"
)
PLACEHOLDER = re.compile(
    r"(?i)your|x{3,}|<|>|\{|\}|\$|example|changeme|placeholder|dummy|password_here|enter|\*{3}"
)
CODE_REF = re.compile(r"(?i)^(os\.|env|getpass|config|self\.|args\.|input\(|[\w.]+\()")
FIXTURE = re.compile(
    r"(?i)fake|dummy|fixture|smoke[_ -]?test|example|placeholder|(^|/)tests?/"
)
SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def git(repo, *args, binary=False, check=True):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    if check and r.returncode:
        raise SystemExit(
            f"git {' '.join(args[:3])} failed: {r.stderr.decode('utf-8', 'replace').strip()[-300:]}"
        )
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def blob(repo, commit, path):
    r = subprocess.run(
        ["git", "-C", repo, "show", f"{commit}:{path}"], capture_output=True
    )
    return r.stdout if r.returncode == 0 else None


def ext_of(path):
    name = path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


# ---------- masking (from repo-security-audit) ----------


def text_lines(text):
    """Lines numbered the way gitleaks and GitHub number them: split on \\n, trailing \\r dropped."""
    if "\n" not in text and "\r" in text:
        return text.split("\r")
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def mask_digits(s):
    return re.sub(r"\d(?=\d{2})", "*", s)


def shape(s, limit=80):
    """Content-free outline of a line (letters -> a, digits -> 9): shows structure, reveals nothing."""
    s = re.sub(r"[^\W\d_]", "a", s)
    s = re.sub(r"\d", "9", s)
    return re.sub(
        r"(a{4})a+|(9{4})9+", lambda m: (m.group(1) or m.group(2)) + "+", s.strip()
    )[:limit]


TOKENISH = re.compile(
    r"[A-Za-z0-9+/=_\-.]{16,}|\b(?=[A-Za-z_]*\d)(?=\d*[A-Za-z])[A-Za-z0-9_\-]{8,}\b"
)


def mask_text(s, limit=140):
    s = re.sub(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@", r"\1***@", s)
    s = re.sub(
        r"(?i)((?:pass|password|passwd|pwd|secret|token|key)\w*[\"']?\s*[:=]\s*[\"']?)([^\s\"'&;,)]{2})"
        r"[^\s\"'&;,)]*",
        r"\1\2…",
        s,
    )
    s = TOKENISH.sub(lambda m: m.group()[:4] + "…", s)
    s = re.sub(r"\d{5,}", lambda m: mask_digits(m.group()), s)
    return s.strip()[:limit]


KEEP_WORDS = re.compile(
    r"(?i)^(pass|password|passwd|pwd|user|username|uid|host|port|db|dbname|database|server|key|"
    r"secret|token|api|client|identified|by|create|alter|role|login|jdbc|oracle|thin|https?|"
    r"postgres|postgresql|mysql|ldap|ftp|sftp|accountkey|sig|sv)$"
)


def shape_keep(s, limit=140):
    """shape() for data/document lines, keeping credential keywords: rows there hold names, not code."""
    return re.sub(
        r"[^\W\d_]+|\d+",
        lambda m: m.group() if KEEP_WORDS.match(m.group()) else shape(m.group()),
        s.strip(),
    )[:limit]


def mask_line(line, path, value=None):
    """A flagged line with its secret cut to 4 characters, then generic masking; data rows become shapes."""
    if value and value in line:
        line = line.replace(value, value[:4] + "…")
    masked = mask_text(line)
    return shape_keep(masked) if ext_of(path) in DATA_EXT else masked


def secret_value(raw, match):
    """The secret itself, from gitleaks' redacted Match (prefix + REDACTED + suffix). Memory only."""
    pre, sep, post = (match or "").partition("REDACTED")
    if not sep or not raw:
        return ""
    for m in re.finditer(
        re.escape(pre) + r"(.+?)" + re.escape(post) + ("$" if not post else ""), raw
    ):
        if m.group(1):
            return m.group(1)
    return ""


def verdict(value):
    if not value:
        return "unknown"
    return (
        "placeholder"
        if PLACEHOLDER.search(value)
        else "code reference"
        if CODE_REF.search(value)
        else "looks real"
    )


def fingerprint(value):
    return hashlib.sha256(SALT + value.encode("utf-8", "replace")).hexdigest()[:12]


# ---------- PII (from repo-security-audit) ----------


def norm_col(h):
    h = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", h.strip(" \"'"))
    return re.sub(r"[^a-z0-9]+", "_", h.lower()).strip("_")


NOT_ID_COL = re.compile(
    r"_(date|dt|time|ts|at|count|cnt|flag|ind|type|sent|domain|status|verified)$"
)
SENSITIVE_PATH = re.compile(
    r"(?i)covid|contact[_ -]?trac|vaccin|test[_ -]?result|quarantin|health|medical|"
    r"counsel|disabilit|accommodat|disciplinary|background[_ -]?check|benefits"
)


def luhn_ok(s):
    d = [int(c) for c in re.sub(r"\D", "", s)]
    if not 13 <= len(d) <= 19 or d[0] not in (3, 4, 5, 6):
        return False
    total = sum(
        x if i % 2 == 0 else (x * 2 - 9 if x > 4 else x * 2)
        for i, x in enumerate(reversed(d))
    )
    return total % 10 == 0


class PiiScanner:
    def __init__(self, cfg):
        self.ids = {k: re.compile(v, re.I) for k, v in cfg["identifiers"].items()}
        self.ignore = re.compile(cfg["ignore_values"])
        self.id_cols = re.compile(cfg["identifier_columns"], re.I)
        self.high_cols = (
            re.compile(cfg["high_columns"], re.I) if cfg.get("high_columns") else None
        )
        self.quasi_cols = (
            re.compile(cfg["quasi_columns"], re.I) if cfg.get("quasi_columns") else None
        )

    def scan(self, lines, tabular):
        """lines: list of text lines. Returns counts and line indexes, never values."""
        hits = {}
        for name, rx in self.ids.items():
            vals, where = set(), []
            for i, line in enumerate(lines):
                found = [
                    m.group()
                    for m in rx.finditer(line)
                    if not self.ignore.search(m.group())
                    and (name != "card" or luhn_ok(m.group()))
                ]
                if found:
                    vals.update(found)
                    if len(where) < 25:
                        where.append(i)
            if vals:
                hits[name] = {"distinct": len(vals), "lines": where}
        text = "\n".join(lines)
        if "org_id" not in hits and self.id_cols.search(
            text
        ):  # pandas prints zero-padded IDs as ints, dropping the leading 0
            rx = re.compile(r"(?<![\d.\-])[1-9]\d{7,8}(?![\d.\-])")
            unpadded = {
                m.group()
                for m in rx.finditer(text)
                if not self.ignore.search(m.group())
            }
            if len(unpadded) >= 5:
                hits["org_id_unpadded"] = {
                    "distinct": len(unpadded),
                    "lines": [i for i, row in enumerate(lines) if rx.search(row)][:25],
                }
        result = {
            "nlines": max(len(lines) - 1, 0) if tabular else len(lines),
            "hits": hits,
        }
        if tabular and lines:
            delim = (
                max("\t,;|", key=lines[0].count)
                if any(c in lines[0] for c in "\t,;|")
                else "\t"
            )
            header = lines[0].split(delim)
            cols = (
                [norm_col(h) for h in header if len(h) <= 50]
                if len(header) >= 2
                else []
            )

            def match(rx, skip=None):
                return (
                    sorted(
                        {
                            m.group()
                            for c in cols
                            if not (skip and skip.search(c))
                            for m in rx.finditer(c)
                        }
                    )
                    if rx
                    else []
                )

            result["identifier_columns"] = match(self.id_cols, NOT_ID_COL)
            result["high_columns"] = match(self.high_cols)
            result["quasi_columns"] = match(self.quasi_cols)
            if "name" in cols and result["high_columns"]:
                result["identifier_columns"] = sorted(
                    set(result["identifier_columns"]) | {"name"}
                )
        return result


def pii_severity(r, path):
    h = r["hits"]
    ids = sum(
        h[k]["distinct"]
        for k in (
            "org_id",
            "org_id_unpadded",
            "id_literal",
            "ssn",
            "ssn_ctx",
            "dob_literal",
        )
        if k in h
    )
    rows = r["nlines"]
    id_cols = r.get("identifier_columns")
    if any(k in h for k in ("ssn", "ssn_ctx", "dob_literal", "card")):
        return "high"
    if id_cols and rows and (r.get("high_columns") or rows >= 20):
        return "high"
    if ids >= 10 or (ids and SENSITIVE_PATH.search(path)):
        return "high"
    if ids or (id_cols and rows):
        return "medium"
    if len(r.get("quasi_columns", [])) >= 3 and rows >= 10:
        return "medium"
    if (
        ext_of(path) in DATA_EXT
        and max(h.get("ip", {}).get("distinct", 0), h.get("mac", {}).get("distinct", 0))
        >= 10
    ):
        return "medium"
    if (
        h.get("email", {}).get("distinct", 0) >= 10
        or h.get("phone", {}).get("distinct", 0) >= 3
    ):
        return "medium"
    return "low" if h else None


def cred_file_rule(path):
    name = path.rsplit("/", 1)[-1]
    if ENVFILE.search(path) and not ENV_OK.search(name):
        return "tracked-env-file", "high"
    if KEYFILE.search(path) and not re.search(r"(?i)public|\.pub$|_pub\.", name):
        return "key-or-cred-file", "high"
    if ENCFILE.search(path):
        return "encrypted-secret-file", "medium"
    return None


# ---------- documents (stdlib only; PDF needs pypdf) ----------


def _xml_text(xml):
    return (
        re.sub(r"<[^>]+>", "", xml)
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
        .replace("&amp;", "&")
    )


def xlsx_lines(z):
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        xml = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        shared = [_xml_text(si) for si in re.findall(r"<si>(.*?)</si>", xml, re.S)]
    out = []
    for name in sorted(
        n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)
    ):
        xml = z.read(name).decode("utf-8", "replace")
        for row in re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S):
            cells = []
            for attrs, body in re.findall(r"<c([^>]*)>(.*?)</c>", row, re.S):
                v = re.search(r"<v>(.*?)</v>", body, re.S)
                t = re.search(r"<t[^>]*>(.*?)</t>", body, re.S)
                if (
                    't="s"' in attrs
                    and v
                    and v.group(1).isdigit()
                    and int(v.group(1)) < len(shared)
                ):
                    cells.append(shared[int(v.group(1))])
                else:
                    cells.append(_xml_text((v or t).group(1)) if (v or t) else "")
            out.append("\t".join(cells))
    return out


def extract_lines(path, data):
    """(lines, tabular) for a file the scanner can read, else None (listed as not inspected)."""
    ext = ext_of(path)
    try:
        if ext in ("xlsx", "xlsm"):
            return xlsx_lines(zipfile.ZipFile(io.BytesIO(data))), True
        if ext == "docx":
            xml = (
                zipfile.ZipFile(io.BytesIO(data))
                .read("word/document.xml")
                .decode("utf-8", "replace")
            )
            return [
                _xml_text(p) for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
            ], False
        if ext == "pptx":
            z = zipfile.ZipFile(io.BytesIO(data))
            return [
                _xml_text(t)
                for n in sorted(z.namelist())
                if re.match(r"ppt/slides/slide\d+\.xml$", n)
                for t in re.findall(
                    r"<a:t>(.*?)</a:t>", z.read(n).decode("utf-8", "replace"), re.S
                )
            ], False
        if ext == "pdf":
            try:
                import pypdf
            except ImportError:
                return None
            reader = pypdf.PdfReader(io.BytesIO(data))
            return [
                ln for pg in reader.pages for ln in text_lines(pg.extract_text() or "")
            ], False
        if ext == "ipynb":
            nb = json.loads(data.decode("utf-8", "replace"))
            out = []
            for cell in nb.get("cells", []):
                out += text_lines("".join(cell.get("source", [])))
                for o in cell.get("outputs", []):
                    out += text_lines(
                        "".join(
                            o.get("text", []) or o.get("data", {}).get("text/plain", [])
                        )
                    )
            return out, False
    except Exception:  # corrupt or password-protected: list it, never call it clean
        return None
    if ext in TEXT_EXT or (b"\0" not in data[:8192] and ext not in DATA_EXT):
        return text_lines(data.decode("utf-8", "replace")), ext in TABULAR
    return None


def doc_secrets(lines, code=False):
    """[(value, line index)] for credentials typed into documents or notebooks; values stay in memory."""
    out, seen = [], set()
    for i, line in enumerate(lines):
        if len(line) > 400:
            continue
        for rx in (DOC_SECRET, URI_SECRET):
            for m in rx.finditer(line):
                value = m.group(1)
                if rx is DOC_SECRET and re.match(
                    r"(?i)[\w.]*\(|os\.|config|getpass|self\.|args\.", value
                ):
                    continue
                if (
                    code
                    and rx is DOC_SECRET
                    and line[m.start(1) - 1 : m.start(1)] not in ("'", '"')
                ):
                    continue
                if value not in seen:
                    seen.add(value)
                    out.append((value, i))
    return out[:20]


# ---------- the branch ----------


def changed_blobs(repo, rng):
    """[(commit, path, blob sha, status)] for every file added or modified by a commit in the range."""
    out, commit = [], None
    for line in git(
        repo,
        "log",
        "--raw",
        "--no-renames",
        "--no-abbrev",
        "--no-merges",
        "--format=@%H",
        rng,
    ).splitlines():
        if line.startswith("@"):
            commit = line[1:]
        elif line.startswith(":"):
            meta, path = line.split("\t", 1)
            parts = meta.split()
            if parts[4][0] in "AM" and parts[1] != "160000":
                out.append((commit, path, parts[3], parts[4][0]))
    return out


def added_lines(repo, rng):
    """{(commit, path): [(line number, text)]} for lines each commit in the range adds."""
    return parse_patch(
        git(
            repo,
            "log",
            "-p",
            "--unified=0",
            "--no-renames",
            "--no-merges",
            "--no-color",
            "--no-ext-diff",
            "--format=@%H",
            rng,
        )
    )


def merge_lines(repo, rng):
    """Like added_lines, for what each merge commit adds beyond the automatic merge (conflict resolutions).
    None when git is too old for --remerge-diff (2.36+)."""
    r = subprocess.run(
        [
            "git",
            "-C",
            repo,
            "log",
            "-p",
            "--remerge-diff",
            "--merges",
            "--unified=0",
            "--no-renames",
            "--no-color",
            "--no-ext-diff",
            "--format=@%H",
            rng,
        ],
        capture_output=True,
    )
    return (
        parse_patch(r.stdout.decode("utf-8", "replace")) if r.returncode == 0 else None
    )


def parse_patch(raw):
    out, commit, path, n = {}, None, None, 0
    for line in raw.split("\n"):
        if line.startswith("@") and not line.startswith("@@"):
            commit = line[1:]
        elif line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            n = int(m.group(1)) if m else 0
        elif line.startswith("+") and path:
            out.setdefault((commit, path), []).append((n, line[1:].rstrip("\r")))
            n += 1
    return out


def gitleaks(args, stdin=None):
    """gitleaks findings (redacted) for `gitleaks git <repo> --log-opts=...` or `gitleaks stdin`."""
    if not shutil.which("gitleaks"):
        raise SystemExit(
            "gitleaks is not on PATH. Install it (winget install Gitleaks.Gitleaks | brew install "
            "gitleaks | https://github.com/gitleaks/gitleaks/releases), then re-run."
        )
    empty = tempfile.mkdtemp(
        prefix="prcheck_noignore_"
    )  # no .gitleaksignore in the branch can silence findings
    try:
        r = subprocess.run(
            [
                "gitleaks",
                *args,
                "--config",
                os.path.join(HERE, "gitleaks_extra.toml"),
                "--redact=100",
                "--report-format",
                "json",
                "--report-path",
                "-",
                "--no-banner",
                "--log-level",
                "error",
                "--exit-code",
                "99",
                "--ignore-gitleaks-allow",
                "--gitleaks-ignore-path",
                empty,
                "--max-target-megabytes",
                "50",
            ],
            input=stdin,
            capture_output=True,
        )
    finally:
        shutil.rmtree(empty, ignore_errors=True)
    if r.returncode not in (0, 99):
        raise SystemExit(
            "gitleaks failed: " + r.stderr.decode("utf-8", "replace").strip()[-300:]
        )
    out = r.stdout.decode("utf-8", "replace").strip()
    return json.loads(out) if out.startswith("[") else []


def nb_image_outputs(data):
    try:
        nb = json.loads(data.decode("utf-8", "replace"))
    except ValueError:
        return 0
    return sum(
        any(k.startswith("image/") for k in o.get("data", {}))
        for c in nb.get("cells", [])
        for o in c.get("outputs", [])
    )


def text_findings(items, pii, add, prose=False, head_text=lambda label: None):
    """Findings in lines that have no file to re-read: merge resolutions, commit messages, a PR body.
    items: [(commit or None, file label, line number, text)]; head_text(label) is that file at HEAD, if any."""
    if not items:
        return
    texts = [t for *_, t in items]
    for lk in gitleaks(["stdin"], stdin="\n".join(texts).encode("utf-8")):
        n = lk.get("StartLine") or 0
        if not 0 < n <= len(items):
            continue
        commit, label, line, raw = items[n - 1]
        value = secret_value(raw, lk.get("Match"))
        v = verdict(value)
        head = head_text(label)
        add(
            {
                "kind": "secret",
                "rule": lk.get("RuleID"),
                "file": label,
                "line": line,
                "severity": "critical" if v == "looks real" else "low",
                "verdict": v,
                "fixture_hint": bool(FIXTURE.search(label)),
                "in_head": bool(value and head and value in head),
                "fingerprint": fingerprint(value) if value else None,
                "masked": mask_line(raw, label, value),
            },
            commit,
        )
    if prose:  # typed credentials gitleaks has no rule for ("the password is ..." in a message)
        for value, i in doc_secrets(texts):
            commit, label, line, raw = items[i]
            v = verdict(value)
            add(
                {
                    "kind": "secret",
                    "rule": "typed-credential",
                    "file": label,
                    "line": line,
                    "severity": "critical" if v == "looks real" else "low",
                    "verdict": v,
                    "fixture_hint": False,
                    "in_head": None,
                    "fingerprint": fingerprint(value),
                    "masked": shape_keep(mask_text(raw)),
                },
                commit,
            )
    groups = {}
    for item in items:
        groups.setdefault((item[0], item[1]), []).append(item)
    for (commit, label), rows in groups.items():
        r = pii.scan([t for *_, t in rows], False)
        sev = pii_severity(r, label)
        if sev in ("high", "medium"):
            first = min(i for h in r["hits"].values() for i in h["lines"])
            add(
                {
                    "kind": "pii",
                    "rule": "+".join(sorted(r["hits"])),
                    "file": label,
                    "line": rows[first][2],
                    "severity": sev,
                    "distinct": {k: h["distinct"] for k, h in r["hits"].items()},
                    "in_head": head_text(label) is not None,
                    "masked": shape(rows[first][3]),
                },
                commit,
            )


def group(findings):
    """One secret in many commits or files is one item: keep the first occurrence, list the rest."""
    grouped, by_fp = [], {}
    for f in sorted(
        findings, key=lambda f: (SEV_ORDER[f["severity"]], f["file"], f["line"])
    ):
        fp = f.get("fingerprint")
        if fp and fp in by_fp:
            g = by_fp[fp]
            g["also_at"].append(
                f"{f['file']}:{f['line']}" + (f"@{f['commit']}" if f["commit"] else "")
            )
            g["pushed"] = g["pushed"] or f["pushed"]
            g["in_head"] = g["in_head"] or f["in_head"]
            continue
        f["also_at"] = []
        if fp:
            by_fp[fp] = f
        grouped.append(f)
    for i, f in enumerate(grouped, 1):
        f["id"] = f"S{i}"
    return grouped


def write_report(a, report):
    grouped = report["findings"]
    report["counts"] = {s: sum(f["severity"] == s for f in grouped) for s in SEV_ORDER}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)
    head = (
        f"{report['commits_scanned']} commits scanned ({report['unpushed_commits']} not pushed); "
        if "commits_scanned" in report
        else ""
    )
    print(
        head
        + f"{len(grouped)} findings "
        + ", ".join(f"{n} {s}" for s, n in report["counts"].items() if n)
        + (
            f"; {len(report['not_inspected'])} not inspected"
            if report.get("not_inspected")
            else ""
        )
        + (f" -> {a.out}" if a.out else "")
    )
    for f in grouped:
        print(
            f"  {f['id']} {f['severity']:8} {f['kind']:9} {f['file']}:{f['line']}  {f.get('masked') or ''}"
        )
    for n in report.get("not_inspected", []):
        print(f"  not inspected: {n['file']} ({n['reason']})")
    return 1 if grouped else 0


def scan_text(a):
    """A PR description draft (or any text file) before it's posted."""
    pii = PiiScanner(json.load(open(a.patterns, encoding="utf-8")))
    with open(a.text, encoding="utf-8", errors="replace") as fh:
        lines = text_lines(fh.read())
    findings = []

    def add(f, commit):
        f["commit"], f["pushed"] = None, False
        findings.append(f)

    text_findings(
        [(None, "(text)", i, t) for i, t in enumerate(lines, 1)], pii, add, prose=True
    )
    return write_report(
        a, {"text": a.text, "findings": group(findings), "not_inspected": []}
    )


def scan(a):
    repo, head = a.repo, git(a.repo, "rev-parse", a.head).strip()
    base = git(a.repo, "rev-parse", a.base).strip()
    rng = f"{base}..{head}"
    commits = git(repo, "rev-list", "--no-merges", rng).split()
    unpushed = set(git(repo, "rev-list", rng, "--not", "--remotes").split())
    cfg = json.load(open(a.patterns, encoding="utf-8"))
    pii = PiiScanner(cfg)
    findings, not_inspected, low = [], [], 0
    head_cache = {}

    def at_head(path):
        if path not in head_cache:
            data = blob(repo, head, path)
            head_cache[path] = (
                data.decode("utf-8", "replace") if data is not None else None
            )
        return head_cache[path]

    def add(f, commit):
        f["commit"] = commit[:12] if commit else None
        f["pushed"] = bool(commit) and commit not in unpushed
        findings.append(f)

    # secrets gitleaks finds in the lines each commit adds
    for lk in gitleaks(["git", repo, f"--log-opts={rng}"]):
        path, commit, n = (
            lk.get("File", ""),
            lk.get("Commit", ""),
            lk.get("StartLine") or 0,
        )
        data = blob(repo, commit, path)
        lines = text_lines(data.decode("utf-8", "replace")) if data else []
        raw = lines[n - 1] if 0 < n <= len(lines) else ""
        value = secret_value(raw, lk.get("Match"))
        v = verdict(value)
        head_text = at_head(path)
        add(
            {
                "kind": "secret",
                "rule": lk.get("RuleID"),
                "file": path,
                "line": n,
                "severity": "critical" if v == "looks real" else "low",
                "verdict": v,
                "fixture_hint": bool(FIXTURE.search(path)),
                "in_head": bool(value and head_text and value in head_text),
                "fingerprint": fingerprint(value) if value else None,
                "masked": mask_line(raw, path, value)
                if raw
                else shape(lk.get("Match") or ""),
            },
            commit,
        )

    # key/credential files, data files and documents added or changed in the range
    seen_blobs, flagged_paths = set(), set()
    added = added_lines(repo, rng)
    for commit, path, sha, status in changed_blobs(repo, rng):
        if VENDORED.search(path):
            continue
        rule = cred_file_rule(path)
        if rule and path not in flagged_paths:
            flagged_paths.add(path)
            add(
                {
                    "kind": "cred_file",
                    "rule": rule[0],
                    "file": path,
                    "line": 0,
                    "severity": rule[1],
                    "in_head": at_head(path) is not None,
                    "masked": None,
                },
                commit,
            )
        if sha in seen_blobs:
            continue
        seen_blobs.add(sha)
        ext = ext_of(path)
        is_data = ext in DATA_EXT or ext in OPENABLE
        size = int(git(repo, "cat-file", "-s", sha).strip() or 0)
        if size > MAX_BYTES:
            not_inspected.append(
                {
                    "file": path,
                    "commit": commit[:12],
                    "reason": f"larger than {MAX_BYTES >> 20} MB",
                }
            )
            continue
        if ext in IMAGE_EXT:  # screenshots of query results are a common way IDs leak
            not_inspected.append(
                {
                    "file": path,
                    "commit": commit[:12],
                    "reason": "image: a person must look at it",
                }
            )
            continue
        if size < 1024:
            small = git(repo, "cat-file", "blob", sha, binary=True)
            if small.startswith(
                LFS_POINTER
            ):  # the content lives on the LFS server, not in git
                not_inspected.append(
                    {"file": path, "commit": commit[:12], "reason": "Git LFS object"}
                )
                if status == "A":
                    add(
                        {
                            "kind": "data_file",
                            "rule": "lfs-file-added",
                            "file": path,
                            "line": 0,
                            "severity": "medium",
                            "in_head": at_head(path) is not None,
                            "masked": None,
                            "inspected": False,
                        },
                        commit,
                    )
                continue
        if (
            is_data
        ):  # whole file: a changed extract is a problem wherever the rows came from
            data = git(repo, "cat-file", "blob", sha, binary=True)
            if ext == "ipynb" and nb_image_outputs(data):
                not_inspected.append(
                    {
                        "file": path,
                        "commit": commit[:12],
                        "reason": f"{nb_image_outputs(data)} image outputs: a person must look at them",
                    }
                )
            got = extract_lines(path, data)
            if got is None:
                not_inspected.append(
                    {
                        "file": path,
                        "commit": commit[:12],
                        "reason": "binary or unreadable format",
                    }
                )
                if status == "A":
                    add(
                        {
                            "kind": "data_file",
                            "rule": "data-file-added",
                            "file": path,
                            "line": 0,
                            "severity": "medium",
                            "in_head": at_head(path) is not None,
                            "masked": None,
                            "inspected": False,
                        },
                        commit,
                    )
                continue
            lines, tabular = got
            numbered = list(enumerate(lines, 1))
        else:  # code and config: only the lines this commit adds
            numbered = added.get((commit, path), [])
            lines, tabular = [t for _, t in numbered], False
        if not numbered:
            continue
        r = pii.scan(lines, tabular)
        sev = pii_severity(r, path)
        if sev == "low":
            low += 1
        if sev in ("high", "medium"):
            first = (
                min(i for h in r["hits"].values() for i in h["lines"])
                if r["hits"]
                else 0
            )
            add(
                {
                    "kind": "pii",
                    "rule": "+".join(sorted(r["hits"])) or "identifier-columns",
                    "file": path,
                    "line": numbered[first][0],
                    "severity": sev,
                    "distinct": {k: h["distinct"] for k, h in r["hits"].items()},
                    "rows": r["nlines"] if tabular else None,
                    "identifier_columns": r.get("identifier_columns"),
                    "high_columns": r.get("high_columns"),
                    "in_head": at_head(path) is not None,
                    "masked": shape(numbered[first][1]) if numbered else None,
                },
                commit,
            )
        elif is_data and status == "A":
            add(
                {
                    "kind": "data_file",
                    "rule": "data-file-added",
                    "file": path,
                    "line": 0,
                    "severity": "low",
                    "rows": r["nlines"] if tabular else None,
                    "in_head": at_head(path) is not None,
                    "masked": None,
                    "inspected": True,
                },
                commit,
            )
        if (
            ext in OPENABLE
        ):  # credentials typed into documents and notebooks; gitleaks can't read these
            for value, i in doc_secrets(lines, code=ext == "ipynb"):
                v = verdict(value)
                add(
                    {
                        "kind": "secret",
                        "rule": "document-credential",
                        "file": path,
                        "line": numbered[i][0],
                        "severity": "critical" if v == "looks real" else "low",
                        "verdict": v,
                        "fixture_hint": bool(FIXTURE.search(path)),
                        "in_head": at_head(path) is not None,
                        "fingerprint": fingerprint(value),
                        "masked": shape_keep(mask_text(lines[i])),
                    },
                    commit,
                )

    # what merge commits add while resolving conflicts: never in a non-merge commit's diff
    merged = merge_lines(repo, rng)
    if merged is None:
        if git(repo, "rev-list", "--merges", rng).split():
            not_inspected.append(
                {
                    "file": "(merge commits)",
                    "commit": None,
                    "reason": "git 2.36+ is needed to check conflict resolutions",
                }
            )
    else:
        items = []
        for (commit, path), rows in merged.items():
            if not VENDORED.search(path) and ext_of(path) not in IMAGE_EXT:
                items += [(commit, path, n, t) for n, t in rows]
        text_findings(items, pii, add, head_text=at_head)

    # commit messages: connection strings and IDs get pasted there too
    items, commit = [], None
    for line in git(repo, "log", "--format=@%H%n%B", rng).splitlines():
        if line.startswith("@") and re.fullmatch(r"@[0-9a-f]{40}", line):
            commit, n = line[1:], 0
            continue
        n += 1
        items.append((commit, "(commit message)", n, line))
    text_findings(items, pii, add, prose=True)

    report = {
        "base": base,
        "head": head,
        "commits_scanned": len(commits),
        "unpushed_commits": len(unpushed),
        "findings": group(findings),
        "not_inspected": not_inspected,
        "low_pii_files": low,
    }
    return write_report(a, report)


def peek(a):
    """Masked view of the lines around FILE:LINE at a commit, for reading a flagged spot without its values."""
    path, _, n = a.peek.rpartition(":")
    if not path or not n.isdigit():
        raise SystemExit("--peek takes FILE:LINE")
    data = blob(a.repo, a.commit, path)
    if data is None:
        raise SystemExit(f"{path} not found at {a.commit}")
    got = extract_lines(path, data)
    if got is None:
        raise SystemExit(f"{path} can't be read as text; a person should open it")
    lines, n = got[0], int(n)
    data_file = ext_of(path) in DATA_EXT
    for i in range(max(1, n - a.context), min(len(lines), n + a.context) + 1):
        line = lines[i - 1]
        shown = shape(line, 140) if data_file else mask_text(line)
        for value, _ in doc_secrets([line]):
            shown = shown.replace(value, value[:2] + "…")
        print(f"{'>' if i == n else ' '}{i:5} {shown}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", help="the merge base with the PR's base branch")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument(
        "--out", help="report path; keep it in the ledger directory, inside .git"
    )
    ap.add_argument("--patterns", default=os.path.join(HERE, "pii_patterns.json"))
    ap.add_argument("--peek", help="FILE:LINE to show masked")
    ap.add_argument(
        "--text",
        help="scan this text file (a draft PR description) instead of the branch",
    )
    ap.add_argument("--commit", default="HEAD")
    ap.add_argument("--context", type=int, default=3)
    a = ap.parse_args()
    try:
        if a.peek:
            return peek(a)
        if a.text:
            return scan_text(a)
        if not a.base or not a.out:
            raise SystemExit("--base and --out are required for a scan")
        return scan(a)
    except SystemExit as e:
        if isinstance(e.code, str):
            print(f"SCAN FAILED: {e.code}", file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())

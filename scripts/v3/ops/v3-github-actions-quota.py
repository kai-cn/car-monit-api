#!/usr/bin/env python3
"""Read-only GitHub Actions quota / billing / workflow probe.

The token is read at runtime from `git credential fill` (Git Credential Manager).
It is NEVER printed, logged or written to disk. The script only emits aggregated
numbers so it is safe to keep its output in the evidence directory.

Usage:
  python v3-github-actions-quota.py [owner/repo]

Output is a plain-text report; exit 0 means the probe itself ran (individual API
calls may report 403/404 and are recorded as such).
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request

UA = {"User-Agent": "car-monit-v3-ops/1.0", "Accept": "application/vnd.github+json"}


def get_token():
    p = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, timeout=30,
    )
    for line in p.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    return ""


def api(path, token):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={**UA, **({"Authorization": "Bearer " + token} if token else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.reason}
    except Exception as e:  # network / proxy failure
        return -1, {"error": "%s: %s" % (type(e).__name__, e)}


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "kai-cn/car-monit-api"
    owner = repo.split("/")[0]
    token = get_token()
    print("token_present=%s" % bool(token))
    print("repo=%s" % repo)

    st, me = api("/user", token)
    print("\n[identity] http=%s login=%s type=%s" %
          (st, me.get("login", me.get("error", "?")), me.get("type", "?")))

    st, r = api("/repos/" + repo, token)
    print("[repo] http=%s private=%s default_branch=%s permissions=%s" % (
        st, r.get("private", r.get("error", "?")),
        r.get("default_branch", "?"),
        "admin" if r.get("permissions", {}).get("admin") else r.get("permissions", {})))

    for label, path in (
        ("user_billing", "/users/%s/settings/billing/actions" % owner),
        ("org_billing", "/orgs/%s/settings/billing/actions" % owner),
    ):
        st, b = api(path, token)
        if st == 200:
            print("[%s] http=200 included_minutes=%s total_minutes_used=%s "
                  "total_paid_minutes_used=%s breakdown=%s" % (
                      label, b.get("included_minutes"), b.get("total_minutes_used"),
                      b.get("total_paid_minutes_used"),
                      json.dumps(b.get("minutes_used_breakdown", {}), ensure_ascii=False)))
        else:
            print("[%s] http=%s msg=%s" % (label, st, b.get("error", "?")))

    st, wf = api("/repos/%s/actions/workflows?per_page=100" % repo, token)
    if st == 200:
        print("\n[workflows] total_count=%s" % wf.get("total_count"))
        for w in wf.get("workflows", []):
            print("  - %-40s state=%s path=%s" % (w.get("name"), w.get("state"), w.get("path")))
    else:
        print("[workflows] http=%s msg=%s" % (st, wf.get("error", "?")))

    st, runs = api("/repos/%s/actions/runs?per_page=10" % repo, token)
    if st == 200:
        print("\n[recent_runs] total_count=%s" % runs.get("total_count"))
        for x in runs.get("workflow_runs", [])[:10]:
            print("  - %s %-28s status=%s conclusion=%s run_started=%s" % (
                x.get("id"), x.get("name"), x.get("status"),
                x.get("conclusion"), x.get("run_started_at")))
    else:
        print("[recent_runs] http=%s msg=%s" % (st, runs.get("error", "?")))


if __name__ == "__main__":
    main()

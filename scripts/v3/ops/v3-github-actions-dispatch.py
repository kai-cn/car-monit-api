#!/usr/bin/env python3
# ======================================================================
# 文件：scripts/v3/ops/v3-github-actions-dispatch.py
# 用途：运维/构建辅助脚本
# 说明：仅新增中文注释，不改执行逻辑。
# ======================================================================
"""Trigger / inspect native-image GitHub Actions runs without the `gh` CLI.

The token is read at runtime from `git credential fill` (Git Credential Manager).
It is never printed or written to disk.

Subcommands:
  ensure-default  Put the cloud workflow on the DEFAULT branch of each repo.
                  GitHub only exposes workflow_dispatch for workflows present on
                  the default branch, so this is required before dispatching.
  dispatch        POST workflow_dispatch, then locate and report the new run.
  list            List recent workflow_dispatch runs.
  status          Report a run and all of its jobs (status / conclusion / duration).

Examples:
  python v3-github-actions-dispatch.py ensure-default \
      --template templates/native-image-cloud.yml
  python v3-github-actions-dispatch.py dispatch \
      --repo kai-cn/car-monit-api --workflow native-image-cloud.yml \
      --ref car-monit-api-jdk25 --input stage=canary
  python v3-github-actions-dispatch.py status --repo kai-cn/car-monit-api --run-id 12345
"""
import argparse
import base64
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
UA = {"User-Agent": "car-monit-v3-ops/1.0",
      "Accept": "application/vnd.github+json"}
REPOS = ("kai-cn/car-monit-api", "kai-cn/car-monit-backend")


def token():
    # 先读仓库外的本地缓存（由 D:/work/runtime-logs/gh_cred.py 生成），
    # 避免每次 git credential fill 触发 GCM 账号选择弹窗。
    import os
    cache = r"D:\work\runtime-logs\.gh_token_cache"
    try:
        with open(cache, "r", encoding="utf-8") as f:
            t = f.read().strip()
        if t:
            return t
    except Exception:
        pass
    p = subprocess.run(["git", "credential", "fill"],
                       input="protocol=https\nhost=github.com\n\n",
                       capture_output=True, text=True, timeout=30)
    for line in p.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise RuntimeError("no GitHub credential returned by git credential fill")


def api(method, path, tok, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={**UA, "Authorization": "Bearer " + tok,
                 **({"Content-Type": "application/json"} if data else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read()
            return r.status, (json.loads(raw.decode("utf-8")) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw.decode("utf-8"))
        except Exception:
            return e.code, {"error": e.reason, "raw": raw.decode("utf-8", "replace")[:400]}
    except Exception as e:
        return -1, {"error": "%s: %s" % (type(e).__name__, e)}


def cmd_ensure_default(args):
    tok = token()
    content = open(args.template, "rb").read()
    path_ = args.path
    for repo in (args.repos.split(",") if args.repos else REPOS):
        st, cur = api("GET", "/repos/%s/contents/%s?ref=master" % (repo, path_), tok)
        sha = cur.get("sha") if st == 200 else None
        body = {"message": "ci(native): add/update " + path_,
                "content": base64.b64encode(content).decode("ascii"),
                "branch": "master"}
        if sha:
            body["sha"] = sha
        st2, res = api("PUT", "/repos/%s/contents/%s" % (repo, path_), tok, body)
        if st2 in (200, 201):
            print("OK   %-28s master/%s commit=%s" % (
                repo, path_, res.get("commit", {}).get("sha", "?")[:12]))
        else:
            print("FAIL %-28s http=%s msg=%s" % (repo, st2, res.get("message", res.get("error"))))
    return 0


def cmd_dispatch(args):
    tok = token()
    inputs = {}
    for pair in args.input or []:
        k, _, v = pair.partition("=")
        inputs[k] = v
    path_ = "/repos/%s/actions/workflows/%s/dispatches" % (args.repo, args.workflow)
    st, res = api("POST", path_, tok, {"ref": args.ref, "inputs": inputs})
    if st != 204:
        print("DISPATCH_FAIL http=%s msg=%s" % (st, res.get("message", res.get("error"))))
        return 1
    print("DISPATCH_OK repo=%s workflow=%s ref=%s inputs=%s" % (
        args.repo, args.workflow, args.ref, json.dumps(inputs, ensure_ascii=False)))

    # Locate the run created by this dispatch. GitHub does not return a run id.
    before = time.time()
    for _ in range(12):
        time.sleep(3)
        st, runs = api("GET", "/repos/%s/actions/runs?event=workflow_dispatch&per_page=5" % args.repo, tok)
        if st == 200:
            for r in runs.get("workflow_runs", []):
                created = r.get("created_at", "")
                if (r.get("path") or "").endswith(args.workflow):
                    print("RUN id=%s url=%s status=%s created=%s" % (
                        r["id"], r.get("html_url"), r.get("status"), created))
                    return 0
        else:
            print("run lookup http=%s msg=%s" % (st, runs.get("message", runs.get("error"))))
    print("RUN_NOT_YET_VISIBLE (dispatch accepted; check `list` in a moment)")
    return 0


def cmd_list(args):
    tok = token()
    st, runs = api("GET", "/repos/%s/actions/runs?event=workflow_dispatch&per_page=%d"
                   % (args.repo, args.limit), tok)
    if st != 200:
        print("LIST_FAIL http=%s msg=%s" % (st, runs.get("message", runs.get("error"))))
        return 1
    for r in runs.get("workflow_runs", []):
        print("%-14s %-28s status=%-10s conclusion=%-10s branch=%-28s created=%s url=%s" % (
            r["id"], r.get("name"), r.get("status"), r.get("conclusion"),
            r.get("head_branch"), r.get("created_at"), r.get("html_url")))
    return 0


def cmd_status(args):
    tok = token()
    st, r = api("GET", "/repos/%s/actions/runs/%s" % (args.repo, args.run_id), tok)
    if st != 200:
        print("STATUS_FAIL http=%s msg=%s" % (st, r.get("message", r.get("error"))))
        return 1
    print("run_id=%s name=%s status=%s conclusion=%s branch=%s created=%s updated=%s url=%s" % (
        r["id"], r.get("name"), r.get("status"), r.get("conclusion"),
        r.get("head_branch"), r.get("created_at"), r.get("updated_at"), r.get("html_url")))
    st, jobs = api("GET", "/repos/%s/actions/runs/%s/jobs?per_page=100" % (args.repo, args.run_id), tok)
    if st == 200:
        for j in jobs.get("jobs", []):
            print("  job=%-40s status=%-10s conclusion=%-12s started=%s completed=%s" % (
                j.get("name"), j.get("status"), j.get("conclusion"),
                j.get("started_at"), j.get("completed_at")))
            if j.get("conclusion") == "failure":
                for s in j.get("steps", []):
                    if s.get("conclusion") == "failure":
                        print("      FAILED_STEP: %s (number=%s)" % (s.get("name"), s.get("number")))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ensure-default")
    p.add_argument("--template", required=True)
    p.add_argument("--path", default=".github/workflows/native-image-cloud.yml")
    p.add_argument("--repos", default=None)
    p.set_defaults(fn=cmd_ensure_default)

    p = sub.add_parser("dispatch")
    p.add_argument("--repo", required=True)
    p.add_argument("--workflow", default="native-image-cloud.yml")
    p.add_argument("--ref", required=True)
    p.add_argument("--input", action="append", default=[])
    p.set_defaults(fn=cmd_dispatch)

    p = sub.add_parser("list")
    p.add_argument("--repo", required=True)
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("status")
    p.add_argument("--repo", required=True)
    p.add_argument("--run-id", required=True)
    p.set_defaults(fn=cmd_status)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
camofox_adapter.py - wxcj camofox-browser adapter

Wraps camofox-browser HTTP API for wxcj use.
Auto-installs, manages service, injects JS, scrolls pages.

Usage:
    python3 camofox_adapter.py init                  # auto-install & start camofox-browser
    python3 camofox_adapter.py open <URL>            # create tab, navigate to URL
    python3 camofox_adapter.py scroll <TAB_ID>       # irregular scroll (simulate human)
    python3 camofox_adapter.py eval <TAB_ID> <SCRIPT> [--url-map <FILE>]
    python3 camofox_adapter.py images <TAB_ID>       # list page images
    python3 camofox_adapter.py close <TAB_ID>        # close tab
    python3 camofox_adapter.py close-all             # close all tabs for user
    python3 camofox_adapter.py health                # check camofox-browser health
"""

import argparse
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# ─── Force UTF-8 output on Windows ───────────────────────────────────────────
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONUTF8", "1")

# ─── Config ───────────────────────────────────────────────────────────────────

CAMOFOX_PORT = os.getenv("CAMOFOX_PORT", "9377")
CAMOFOX_BASE = f"http://127.0.0.1:{CAMOFOX_PORT}"
CAMOFOX_REPO_URL = os.getenv(
    "CAMOFOX_BROWSER_GIT_URL",
    "https://github.com/jo-inc/camofox-browser.git",
)
CAMOFOX_REPO = Path(
    os.getenv(
        "CAMOFOX_BROWSER_REPO",
        str(Path.home() / ".hermes" / "camofox-browser"),
    )
).expanduser()
CAMOFOX_LOG_DIR = Path(
    os.getenv("CAMOFOX_LOG_DIR", str(Path.home() / ".hermes" / "logs"))
).expanduser()
CAMOFOX_LOG_FILE = CAMOFOX_LOG_DIR / "camofox-browser.log"
CAMOFOX_PID_FILE = CAMOFOX_LOG_DIR / "camofox-browser.pid"
CAMOFOX_INSTALL_TIMEOUT = int(os.getenv("CAMOFOX_INSTALL_TIMEOUT", "18000"))
CAMOFOX_HEALTH_WAIT_SECONDS = int(os.getenv("CAMOFOX_HEALTH_WAIT_SECONDS", "120"))

DEFAULT_USER_ID = "wxcj"
DEFAULT_SESSION_KEY = "batch"


# ─── HTTP ─────────────────────────────────────────────────────────────────────

def _http(method, path, payload=None, timeout=120):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        CAMOFOX_BASE + path, data=data, headers=headers, method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} {method} {path}: {body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Cannot reach camofox-browser at {CAMOFOX_BASE}: {e.reason}")


def _progress(msg):
    print(f"[camofox] {msg}", file=sys.stderr, flush=True)


# ─── Auto install ─────────────────────────────────────────────────────────────

def _require_command(cmd):
    if shutil.which(cmd):
        return
    hints = {"git": "Please install git first.", "npm": "Please install Node.js 18+ (with npm)."}
    raise SystemExit(f"Missing '{cmd}'. {hints.get(cmd, '')}")


def _install_camofox():
    repo = CAMOFOX_REPO
    _require_command("git")
    _require_command("npm")
    repo.parent.mkdir(parents=True, exist_ok=True)

    if not (repo / "server.js").exists():
        _progress(f"Cloning camofox-browser to {repo}")
        subprocess.run(
            ["git", "clone", "--depth", "1", CAMOFOX_REPO_URL, str(repo)],
            check=True, timeout=CAMOFOX_INSTALL_TIMEOUT,
        )
    else:
        _progress(f"Reusing existing repo at {repo}")

    if not (repo / "package.json").exists():
        raise SystemExit(f"Incomplete install at {repo}")

    if not (repo / "node_modules").exists():
        _progress("Running npm install (first time may be slow)")
        subprocess.run(
            ["npm", "install"], cwd=str(repo),
            check=True, timeout=CAMOFOX_INSTALL_TIMEOUT,
        )
    else:
        _progress("npm dependencies already present")

    return repo


def _start_camofox_server(repo):
    _progress(f"Starting camofox-browser on :{CAMOFOX_PORT}")
    CAMOFOX_LOG_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("CAMOFOX_BROWSER_REPO", str(repo))
    env.setdefault("CAMOFOX_PORT", str(CAMOFOX_PORT))

    start_script = shutil.which("camofox-browser-start")
    if start_script:
        subprocess.run(
            [start_script], check=True,
            timeout=CAMOFOX_HEALTH_WAIT_SECONDS, env=env,
        )
        return

    npm_cmd = shutil.which("npm") or "npm"
    with CAMOFOX_LOG_FILE.open("ab") as log_fp:
        proc = subprocess.Popen(
            [npm_cmd, "start"], cwd=str(repo),
            stdout=log_fp, stderr=subprocess.STDOUT,
            start_new_session=True, env=env,
            shell=(os.name == "nt"),
        )
    CAMOFOX_PID_FILE.write_text(str(proc.pid))


def ensure_camofox():
    _progress(f"Checking camofox-browser on :{CAMOFOX_PORT}")
    try:
        _http("GET", "/health", timeout=10)
        _progress("camofox-browser is healthy")
        return
    except SystemExit:
        _progress("camofox-browser not running, bootstrapping now")

    repo = _install_camofox()
    _start_camofox_server(repo)

    _progress(f"Waiting for health check (max {CAMOFOX_HEALTH_WAIT_SECONDS}s)")
    deadline = time.time() + CAMOFOX_HEALTH_WAIT_SECONDS
    while time.time() < deadline:
        try:
            _http("GET", "/health", timeout=10)
            _progress("camofox-browser is healthy")
            return
        except SystemExit:
            time.sleep(2)
    raise SystemExit(
        f"camofox-browser did not become healthy in {CAMOFOX_HEALTH_WAIT_SECONDS}s. "
        f"Check log: {CAMOFOX_LOG_FILE}"
    )


# ─── Core operations ──────────────────────────────────────────────────────────

def cmd_open(url, user_id=DEFAULT_USER_ID, session_key=DEFAULT_SESSION_KEY):
    result = _http("POST", "/tabs", {
        "userId": user_id, "sessionKey": session_key, "url": url,
    }, timeout=120)
    tab_id = result.get("tabId", "")
    if not tab_id:
        raise SystemExit(f"Failed to create tab: {json.dumps(result, ensure_ascii=False)}")
    _progress(f"tab created: {tab_id}")
    return tab_id


def cmd_scroll(tab_id, direction="down", amount=0, user_id=DEFAULT_USER_ID):
    if amount <= 0:
        steps = [
            (random.randint(300, 600), random.randint(400, 1200)),
            (random.randint(400, 800), random.randint(500, 1500)),
            (random.randint(300, 700), random.randint(600, 1800)),
            (random.randint(500, 1000), random.randint(800, 2300)),
            (random.randint(200, 500), random.randint(500, 1500)),
            (random.randint(600, 1500), random.randint(1000, 3000)),
        ]
        for dist, wait_ms in steps:
            _http("POST", f"/tabs/{tab_id}/scroll", {
                "userId": user_id, "direction": direction, "amount": dist,
            })
            time.sleep(wait_ms / 1000.0)
    else:
        _http("POST", f"/tabs/{tab_id}/scroll", {
            "userId": user_id, "direction": direction, "amount": amount,
        })


def cmd_eval(tab_id, script_path, url_map_path=None, user_id=DEFAULT_USER_ID):
    script_file = Path(script_path)
    if not script_file.exists():
        raise SystemExit(f"Script not found: {script_path}")
    script_content = script_file.read_text(encoding="utf-8")

    parts = []
    if url_map_path:
        map_file = Path(url_map_path)
        if map_file.exists():
            map_data = map_file.read_text(encoding="utf-8").strip()
            parts.append(f"window.__urlMap = {map_data};")

    parts.append(script_content)
    expression = "\n".join(parts)

    result = _http("POST", f"/tabs/{tab_id}/evaluate", {
        "userId": user_id, "expression": expression,
    }, timeout=30)

    if not result.get("ok"):
        raise SystemExit(f"JS eval failed: {json.dumps(result, ensure_ascii=False)}")

    raw = result.get("result")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"content": raw, "imgCount": 0}
    elif isinstance(raw, (dict, list)):
        return raw if isinstance(raw, dict) else {"result": raw}
    else:
        return {"content": str(raw), "imgCount": 0}


def cmd_images(tab_id, user_id=DEFAULT_USER_ID):
    result = _http("GET", f"/tabs/{tab_id}/images?userId={user_id}&limit=50", timeout=30)
    if isinstance(result, dict):
        return result.get("images", [])
    return result if isinstance(result, list) else []


def cmd_links(tab_id, user_id=DEFAULT_USER_ID):
    result = _http("GET", f"/tabs/{tab_id}/links?userId={user_id}", timeout=30)
    if isinstance(result, dict):
        return result.get("links", [])
    return []


def cmd_snapshot(tab_id, user_id=DEFAULT_USER_ID):
    result = _http("GET", f"/tabs/{tab_id}/snapshot?userId={user_id}", timeout=60)
    return result.get("snapshot", "")


def cmd_close(tab_id, user_id=DEFAULT_USER_ID):
    try:
        _http("DELETE", f"/tabs/{tab_id}?userId={urllib.parse.quote(user_id)}", timeout=15)
        _progress(f"tab {tab_id} closed")
    except SystemExit:
        pass


def cmd_close_all(user_id=DEFAULT_USER_ID):
    try:
        _http("DELETE", f"/sessions/{urllib.parse.quote(user_id)}", timeout=15)
        _progress(f"session {user_id} closed")
    except SystemExit:
        pass


def cmd_health():
    try:
        result = _http("GET", "/health", timeout=10)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return True
    except SystemExit:
        return False


# ─── Convenience API (for Python import) ──────────────────────────────────────

def fetch_article_via_camofox(url, user_id=DEFAULT_USER_ID):
    tab_id = cmd_open(url, user_id=user_id)
    time.sleep(random.uniform(2, 5))
    cmd_scroll(tab_id, user_id=user_id)

    scripts_dir = Path(__file__).resolve().parent
    content = cmd_eval(tab_id, str(scripts_dir / "extract_content.js"), user_id=user_id)
    images = cmd_eval(tab_id, str(scripts_dir / "extract_images.js"), user_id=user_id)
    meta = cmd_eval(tab_id, str(scripts_dir / "extract_metadata.js"), user_id=user_id)

    cmd_close(tab_id, user_id=user_id)

    return {
        "content": content.get("content", "") if isinstance(content, dict) else "",
        "imgCount": content.get("imgCount", 0) if isinstance(content, dict) else 0,
        "images": images.get("images", []) if isinstance(images, dict) else [],
        "metadata": meta if isinstance(meta, dict) else {},
        "tabId": tab_id,
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="camofox-browser adapter for wxcj")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="auto-install & start camofox-browser")

    p = sub.add_parser("open", help="create tab and navigate")
    p.add_argument("url", help="article URL")
    p.add_argument("--user-id", default=DEFAULT_USER_ID)

    p = sub.add_parser("scroll", help="scroll page (random by default)")
    p.add_argument("tab_id")
    p.add_argument("--direction", default="down", choices=["up", "down"])
    p.add_argument("--amount", type=int, default=0, help="pixels, 0=random")
    p.add_argument("--user-id", default=DEFAULT_USER_ID)

    p = sub.add_parser("eval", help="execute JS in page")
    p.add_argument("tab_id")
    p.add_argument("script", help="JS file path")
    p.add_argument("--url-map", default=None, help="URL mapping JSON file")
    p.add_argument("--user-id", default=DEFAULT_USER_ID)

    p = sub.add_parser("images", help="list page images")
    p.add_argument("tab_id")
    p.add_argument("--user-id", default=DEFAULT_USER_ID)

    p = sub.add_parser("links", help="list page links")
    p.add_argument("tab_id")
    p.add_argument("--user-id", default=DEFAULT_USER_ID)

    p = sub.add_parser("snapshot", help="get accessibility snapshot")
    p.add_argument("tab_id")
    p.add_argument("--user-id", default=DEFAULT_USER_ID)

    p = sub.add_parser("close", help="close tab")
    p.add_argument("tab_id")
    p.add_argument("--user-id", default=DEFAULT_USER_ID)

    p = sub.add_parser("close-all", help="close all tabs for user")
    p.add_argument("--user-id", default=DEFAULT_USER_ID)

    sub.add_parser("health", help="check camofox-browser health")

    args = parser.parse_args()

    if args.command == "init":
        ensure_camofox()
        return 0
    if args.command == "open":
        print(cmd_open(args.url, user_id=args.user_id))
        return 0
    if args.command == "scroll":
        cmd_scroll(args.tab_id, args.direction, args.amount, args.user_id)
        return 0
    if args.command == "eval":
        print(json.dumps(
            cmd_eval(args.tab_id, args.script, args.url_map, args.user_id),
            ensure_ascii=False,
        ))
        return 0
    if args.command == "images":
        print(json.dumps(cmd_images(args.tab_id, args.user_id), ensure_ascii=False))
        return 0
    if args.command == "links":
        print(json.dumps(cmd_links(args.tab_id, args.user_id), ensure_ascii=False))
        return 0
    if args.command == "snapshot":
        print(cmd_snapshot(args.tab_id, args.user_id))
        return 0
    if args.command == "close":
        cmd_close(args.tab_id, args.user_id)
        return 0
    if args.command == "close-all":
        cmd_close_all(args.user_id)
        return 0
    if args.command == "health":
        return 0 if cmd_health() else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

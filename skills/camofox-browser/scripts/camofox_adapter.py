#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
camofox_adapter.py - Generic camofox-browser CLI adapter

Wraps camofox-browser HTTP API for general-purpose browser automation.
Auto-installs, manages service, handles screenshots, login flows, and page interaction.

Usage:
    python3 camofox_adapter.py init                  # auto-install & start camofox-browser
    python3 camofox_adapter.py open <URL>            # create tab, navigate to URL
    python3 camofox_adapter.py screenshot <TAB_ID>   # capture screenshot, save & open
    python3 camofox_adapter.py click <TAB_ID>        # click element by selector or text
    python3 camofox_adapter.py type <TAB_ID>         # type into input field
    python3 camofox_adapter.py wait <TAB_ID>         # wait for element or URL change
    python3 camofox_adapter.py scroll <TAB_ID>       # irregular scroll (simulate human)
    python3 camofox_adapter.py eval <TAB_ID> <SCRIPT> # execute JS in page
    python3 camofox_adapter.py snapshot <TAB_ID>     # accessibility snapshot
    python3 camofox_adapter.py images <TAB_ID>       # list page images
    python3 camofox_adapter.py links <TAB_ID>        # list page links
    python3 camofox_adapter.py close <TAB_ID>        # close tab
    python3 camofox_adapter.py close-all             # close all tabs
    python3 camofox_adapter.py health                # check health
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
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

DEFAULT_USER_ID = "camofox"
DEFAULT_SESSION_KEY = "default"


# ─── HTTP ─────────────────────────────────────────────────────────────────────

def _http(method, path, payload=None, timeout=120, retries=2):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    last_err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            CAMOFOX_BASE + path, data=data, headers=headers, method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise SystemExit(f"HTTP {e.code} {method} {path}: {body}")
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(1)
                continue
    raise SystemExit(f"Cannot reach camofox-browser at {CAMOFOX_BASE}: {last_err}")


def _http_raw(path, timeout=60, retries=2):
    """GET request that returns raw bytes (for binary responses like screenshots)."""
    last_err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(CAMOFOX_BASE + path, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            raise SystemExit(f"HTTP {e.code} GET {path}")
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(1)
                continue
    raise SystemExit(f"Cannot reach camofox-browser at {CAMOFOX_BASE}: {last_err}")


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

    with CAMOFOX_LOG_FILE.open("ab") as log_fp:
        proc = subprocess.Popen(
            ["npm", "start"], cwd=str(repo),
            stdout=log_fp, stderr=subprocess.STDOUT,
            start_new_session=True, env=env,
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


def cmd_screenshot(tab_id, output=None, view=False, user_id=DEFAULT_USER_ID):
    """Capture screenshot as PNG, save to file, optionally open for viewing."""
    data = _http_raw(f"/tabs/{tab_id}/screenshot?userId={user_id}", timeout=30)

    if not data[:4] == b'\x89PNG':
        raise SystemExit("Response is not a valid PNG image")

    if output is None:
        fd, output = tempfile.mkstemp(suffix=".png", prefix="camofox_")
        os.close(fd)

    Path(output).write_bytes(data)
    _progress(f"screenshot saved: {output} ({len(data)} bytes)")

    if view:
        if sys.platform == "win32":
            os.startfile(output)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", output])
        else:
            subprocess.Popen(["xdg-open", output])

    print(output)
    return output


def cmd_click(tab_id, selector=None, text=None, user_id=DEFAULT_USER_ID):
    """Click an element by CSS selector or text content."""
    if selector:
        js = f'''(() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) throw "Element not found: {selector}";
            el.scrollIntoView({{block: "center"}});
            el.click();
            return true;
        }})()'''
    elif text:
        js = f'''(() => {{
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {{
                if (walker.currentNode.textContent.includes({json.dumps(text)})) {{
                    const el = walker.currentNode.parentElement;
                    el.scrollIntoView({{block: "center"}});
                    el.click();
                    return true;
                }}
            }}
            throw "No element containing text: {text}";
        }})()'''
    else:
        raise SystemExit("Must specify --selector or --text")

    result = _http("POST", f"/tabs/{tab_id}/evaluate", {
        "userId": user_id, "expression": js,
    }, timeout=30)
    if not result.get("ok"):
        raise SystemExit(f"Click failed: {json.dumps(result, ensure_ascii=False)}")
    _progress("clicked")


def cmd_type(tab_id, selector, value, user_id=DEFAULT_USER_ID):
    """Type text into an input field, compatible with React/Vue frameworks."""
    js = f'''(() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) throw "Element not found: {selector}";
        el.scrollIntoView({{block: "center"}});
        el.focus();
        el.value = "";
        const nativeSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, "value"
        )?.set || Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, "value"
        )?.set;
        if (nativeSetter) {{
            nativeSetter.call(el, {json.dumps(value)});
        }} else {{
            el.value = {json.dumps(value)};
        }}
        el.dispatchEvent(new Event("input", {{ bubbles: true }}));
        el.dispatchEvent(new Event("change", {{ bubbles: true }}));
        return true;
    }})()'''

    result = _http("POST", f"/tabs/{tab_id}/evaluate", {
        "userId": user_id, "expression": js,
    }, timeout=30)
    if not result.get("ok"):
        raise SystemExit(f"Type failed: {json.dumps(result, ensure_ascii=False)}")
    _progress("typed")


def cmd_wait(tab_id, selector=None, url_pattern=None, timeout=30, user_id=DEFAULT_USER_ID):
    """Wait for an element to appear or URL to match a pattern."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if selector:
            js = f'!!document.querySelector({json.dumps(selector)})'
        elif url_pattern:
            js = f'new RegExp({json.dumps(url_pattern)}).test(location.href)'
        else:
            raise SystemExit("Must specify --selector or --url-pattern")

        result = _http("POST", f"/tabs/{tab_id}/evaluate", {
            "userId": user_id, "expression": js,
        }, timeout=10)

        if result.get("ok"):
            val = result.get("result")
            if isinstance(val, str):
                val = val.strip().lower() in ("true", "1")
            if val:
                _progress("wait condition met")
                return True
        time.sleep(1)

    raise SystemExit(f"Timeout after {timeout}s waiting for condition")


def cmd_scroll(tab_id, direction="down", amount=0, user_id=DEFAULT_USER_ID):
    """Scroll page. amount=0 triggers random human-like scrolling."""
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


def cmd_eval(tab_id, script_or_expr, user_id=DEFAULT_USER_ID):
    """Execute JS in page. Accepts file path or inline expression."""
    script_path = Path(script_or_expr)
    if script_path.exists() and script_path.is_file():
        expression = script_path.read_text(encoding="utf-8")
    else:
        expression = script_or_expr

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


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="camofox-browser generic adapter")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help="User/session ID")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="auto-install & start camofox-browser")

    p = sub.add_parser("open", help="create tab and navigate")
    p.add_argument("url", help="URL to open")
    p.add_argument("--session-key", default=DEFAULT_SESSION_KEY)

    p = sub.add_parser("screenshot", help="capture screenshot")
    p.add_argument("tab_id")
    p.add_argument("--output", "-o", default=None, help="Output file path")
    p.add_argument("--view", action="store_true", help="Open image viewer after saving")

    p = sub.add_parser("click", help="click element")
    p.add_argument("tab_id")
    p.add_argument("--selector", "-s", default=None, help="CSS selector")
    p.add_argument("--text", "-t", default=None, help="Text content to find and click")

    p = sub.add_parser("type", help="type into input field")
    p.add_argument("tab_id")
    p.add_argument("--selector", "-s", required=True, help="CSS selector")
    p.add_argument("--value", "-v", required=True, help="Text to type")

    p = sub.add_parser("wait", help="wait for condition")
    p.add_argument("tab_id")
    p.add_argument("--selector", "-s", default=None, help="Wait for element")
    p.add_argument("--url-pattern", "-u", default=None, help="Wait for URL pattern")
    p.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")

    p = sub.add_parser("scroll", help="scroll page")
    p.add_argument("tab_id")
    p.add_argument("--direction", default="down", choices=["up", "down"])
    p.add_argument("--amount", type=int, default=0, help="Pixels, 0=random")

    p = sub.add_parser("eval", help="execute JS")
    p.add_argument("tab_id")
    p.add_argument("script", help="JS file path or inline expression")

    p = sub.add_parser("images", help="list page images")
    p.add_argument("tab_id")

    p = sub.add_parser("links", help="list page links")
    p.add_argument("tab_id")

    p = sub.add_parser("snapshot", help="get accessibility snapshot")
    p.add_argument("tab_id")

    p = sub.add_parser("close", help="close tab")
    p.add_argument("tab_id")

    sub.add_parser("close-all", help="close all tabs")

    sub.add_parser("health", help="check health")

    args = parser.parse_args()
    user_id = args.user_id

    if args.command == "init":
        ensure_camofox()
        return 0
    if args.command == "open":
        print(cmd_open(args.url, user_id=user_id, session_key=args.session_key))
        return 0
    if args.command == "screenshot":
        cmd_screenshot(args.tab_id, output=args.output, view=args.view, user_id=user_id)
        return 0
    if args.command == "click":
        cmd_click(args.tab_id, selector=args.selector, text=args.text, user_id=user_id)
        return 0
    if args.command == "type":
        cmd_type(args.tab_id, args.selector, args.value, user_id=user_id)
        return 0
    if args.command == "wait":
        cmd_wait(args.tab_id, selector=args.selector, url_pattern=args.url_pattern,
                 timeout=args.timeout, user_id=user_id)
        return 0
    if args.command == "scroll":
        cmd_scroll(args.tab_id, args.direction, args.amount, user_id=user_id)
        return 0
    if args.command == "eval":
        result = cmd_eval(args.tab_id, args.script, user_id=user_id)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.command == "images":
        print(json.dumps(cmd_images(args.tab_id, user_id=user_id), ensure_ascii=False))
        return 0
    if args.command == "links":
        print(json.dumps(cmd_links(args.tab_id, user_id=user_id), ensure_ascii=False))
        return 0
    if args.command == "snapshot":
        print(cmd_snapshot(args.tab_id, user_id=user_id))
        return 0
    if args.command == "close":
        cmd_close(args.tab_id, user_id=user_id)
        return 0
    if args.command == "close-all":
        cmd_close_all(user_id=user_id)
        return 0
    if args.command == "health":
        return 0 if cmd_health() else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

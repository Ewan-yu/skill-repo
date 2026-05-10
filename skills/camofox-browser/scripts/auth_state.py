#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth_state.py - Save and restore browser authentication state

Extracts cookies + localStorage from a camofox-browser tab via JavaScript,
saves them to a JSON file, and can restore them into a new tab later.

Usage:
    python3 auth_state.py save <TAB_ID> --output auth.json [--user-id USER]
    python3 auth_state.py restore <TAB_ID> --input auth.json [--user-id USER]
    python3 auth_state.py check <TAB_ID> [--user-id USER]
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONUTF8", "1")

CAMOFOX_PORT = os.getenv("CAMOFOX_PORT", "9377")
CAMOFOX_BASE = f"http://127.0.0.1:{CAMOFOX_PORT}"
DEFAULT_USER_ID = "camofox"

# ─── JavaScript snippets ─────────────────────────────────────────────────────

SAVE_COOKIES_JS = """(() => {
    const result = {};
    document.cookie.split('; ').forEach(c => {
        const idx = c.indexOf('=');
        if (idx > 0) result[c.substring(0, idx)] = c.substring(idx + 1);
    });
    return JSON.stringify(result);
})()"""

SAVE_LOCALSTORAGE_JS = """(() => {
    const data = {};
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        data[key] = localStorage.getItem(key);
    }
    return JSON.stringify(data);
})()"""

RESTORE_COOKIES_JS = """(() => {{
    const cookies = {cookies_json};
    let count = 0;
    for (const [k, v] of Object.entries(cookies)) {{
        document.cookie = k + '=' + v + '; path=/; max-age=31536000';
        count++;
    }}
    return count;
}})()"""

RESTORE_LOCALSTORAGE_JS = """(() => {{
    const data = {ls_json};
    let count = 0;
    for (const [k, v] of Object.entries(data)) {{
        localStorage.setItem(k, v);
        count++;
    }}
    return count;
}})()"""

CHECK_LOGIN_JS = """(() => {
    return JSON.stringify({
        hasCookies: document.cookie.length > 0,
        cookieCount: document.cookie.split(';').filter(c => c.trim()).length,
        localStorageCount: localStorage.length,
        url: location.href,
        title: document.title
    });
})()"""


# ─── HTTP ─────────────────────────────────────────────────────────────────────

def _eval(tab_id, expression, user_id=DEFAULT_USER_ID):
    """Execute JS in the page and return the result."""
    data = json.dumps({"userId": user_id, "expression": expression}).encode("utf-8")
    req = urllib.request.Request(
        f"{CAMOFOX_BASE}/tabs/{tab_id}/evaluate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as e:
        raise SystemExit(f"Cannot reach camofox-browser: {e.reason}")

    if not result.get("ok"):
        raise SystemExit(f"JS eval failed: {json.dumps(result, ensure_ascii=False)}")

    raw = result.get("result")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_save(tab_id, output, user_id=DEFAULT_USER_ID):
    """Extract cookies + localStorage and save to JSON file."""
    cookies_raw = _eval(tab_id, SAVE_COOKIES_JS, user_id)
    ls_raw = _eval(tab_id, SAVE_LOCALSTORAGE_JS, user_id)

    cookies = json.loads(cookies_raw) if isinstance(cookies_raw, str) else cookies_raw
    localStorage = json.loads(ls_raw) if isinstance(ls_raw, str) else ls_raw

    # Get current URL and domain
    url_info = _eval(tab_id, "JSON.stringify({url: location.href, domain: document.domain})", user_id)
    if isinstance(url_info, str):
        url_info = json.loads(url_info)

    state = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "url": url_info.get("url", ""),
        "domain": url_info.get("domain", ""),
        "cookies": cookies,
        "localStorage": localStorage,
    }

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[auth] saved: {len(cookies)} cookies, {len(localStorage)} localStorage items -> {output}")
    return state


def cmd_restore(tab_id, input_file, user_id=DEFAULT_USER_ID):
    """Inject saved cookies + localStorage into a tab."""
    state = json.loads(Path(input_file).read_text(encoding="utf-8"))

    cookies = state.get("cookies", {})
    localStorage = state.get("localStorage", {})

    if cookies:
        js = RESTORE_COOKIES_JS.format(cookies_json=json.dumps(cookies))
        count = _eval(tab_id, js, user_id)
        print(f"[auth] restored {count} cookies")

    if localStorage:
        js = RESTORE_LOCALSTORAGE_JS.format(ls_json=json.dumps(localStorage))
        count = _eval(tab_id, js, user_id)
        print(f"[auth] restored {count} localStorage items")

    print(f"[auth] restore complete from {input_file}")


def cmd_check(tab_id, user_id=DEFAULT_USER_ID):
    """Check if the current page has an active session."""
    result = _eval(tab_id, CHECK_LOGIN_JS, user_id)
    if isinstance(result, str):
        result = json.loads(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Browser auth state manager")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("save", help="Save auth state to file")
    p.add_argument("tab_id")
    p.add_argument("--output", "-o", required=True, help="Output JSON file")

    p = sub.add_parser("restore", help="Restore auth state from file")
    p.add_argument("tab_id")
    p.add_argument("--input", "-i", required=True, help="Input JSON file")

    p = sub.add_parser("check", help="Check current login status")
    p.add_argument("tab_id")

    args = parser.parse_args()

    if args.command == "save":
        cmd_save(args.tab_id, args.output, user_id=args.user_id)
        return 0
    if args.command == "restore":
        cmd_restore(args.tab_id, args.input, user_id=args.user_id)
        return 0
    if args.command == "check":
        cmd_check(args.tab_id, user_id=args.user_id)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

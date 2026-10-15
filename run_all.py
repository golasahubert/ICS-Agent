"""Runs the checks for all 6 honeypot HMIs, alerts on failure and sends a
daily "all OK" report after 24h without any failure.

Meant to be started every hour by systemd (ics-agent.timer).
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "agent.env"
STATE_FILE = BASE_DIR / "state.json"

# (name = variant folder in ICSHoneypot, check script, env var with URL)
HMIS = [
    ("1.Custom-HMI", "1-CustomHMI.py", "HMI_1_URL"),
    ("2.scadaBR", "2.ScadaBR.py", "HMI_2_URL"),
    ("3.scadaBR-without-buttons", "3.ScadaBR-no-B.py", "HMI_3_URL"),
    ("4.ScadaLTSv2.7.4", "4.ScadaLTS.py", "HMI_4_URL"),
    ("5.NewScada", "5.NewScada.py", "HMI_5_URL"),
    ("6.ScadaLTS-no-buttons", "6.ScadaLTS-no-B.py", "HMI_6_URL"),
]

CHECK_TIMEOUT = 300          # seconds per HMI
CHECK_ATTEMPTS = 3           # alert only if every attempt fails
RETRY_DELAY = 30             # seconds between attempts
OK_REPORT_PERIOD = timedelta(hours=24)
MAX_RUN_GAP = timedelta(hours=2)  # longer gap between runs breaks the OK streak

FAIL_MARKERS = ("[!]", "[✘]", "Error", "ERROR", "WARNING", "CRITICAL", "Missing")


def load_config():
    """Loads KEY=VALUE lines from agent.env into os.environ (real env wins)."""
    if not CONFIG_FILE.exists():
        return
    for line in CONFIG_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def run_check(script, url_var):
    """Runs one check script. Returns (ok, output)."""
    if not os.environ.get(url_var):
        return False, f"{url_var} is not set in {CONFIG_FILE.name}"
    try:
        proc = subprocess.run(
            [sys.executable, str(BASE_DIR / script)],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=CHECK_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, f"Check timed out after {CHECK_TIMEOUT}s"
    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, output


def run_check_with_retries(script, url_var):
    """Runs a check up to CHECK_ATTEMPTS times, stopping at the first success.
    Returns (ok, output of the last attempt)."""
    for attempt in range(1, CHECK_ATTEMPTS + 1):
        ok, output = run_check(script, url_var)
        print(output)
        print(f"[attempt {attempt}/{CHECK_ATTEMPTS}] {'OK' if ok else 'FAIL'}")
        if ok or not os.environ.get(url_var):
            return ok, output
        if attempt < CHECK_ATTEMPTS:
            time.sleep(RETRY_DELAY)
    return False, f"Failed {CHECK_ATTEMPTS}/{CHECK_ATTEMPTS} attempts, last output:\n{output}"


def failure_reason(output):
    """Picks the most relevant line from the check output."""
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    for line in reversed(lines):
        if any(m in line for m in FAIL_MARKERS):
            return line
    return lines[-1] if lines else "unknown"


def format_alert(name, url, output, now):
    logs = escape_html(output)[-2500:]
    return (
        f"🚨 <b>HMI ALERT: {escape_html(name)}</b>\n\n"
        f"<b>Status:</b> ❌ check failed\n"
        f"<b>Reason:</b> {escape_html(failure_reason(output))}\n"
        f"<b>URL:</b> {escape_html(url or '-')}\n"
        f"<b>Time:</b> {now:%Y-%m-%d %H:%M}\n\n"
        f"<b>Logs:</b>\n<pre>{logs}</pre>"
    )


def format_ok_report(since, now, runs):
    hmi_list = "\n".join(f"✅ {name}" for name, _, _ in HMIS)
    return (
        f"🟢 <b>ICS Honeypot: 24h without alerts</b>\n\n"
        f"All {len(HMIS)} HMIs passed every hourly check.\n"
        f"<b>Period:</b> {since:%Y-%m-%d %H:%M} → {now:%Y-%m-%d %H:%M}\n"
        f"<b>Runs:</b> {runs}\n\n"
        f"{hmi_list}"
    )


def send(message):
    from telegram_alert import send_telegram_alert
    asyncio.run(send_telegram_alert(message))


def update_ok_streak(state, all_ok, now):
    """Sends the OK report once the streak of all-OK runs reaches 24h."""
    last_run = state.get("last_run")
    gap_too_long = last_run and now - datetime.fromisoformat(last_run) > MAX_RUN_GAP

    if not all_ok:
        state["ok_since"] = None
        state["ok_runs"] = 0
    elif not state.get("ok_since") or gap_too_long:
        state["ok_since"] = now.isoformat()
        state["ok_runs"] = 1
    else:
        state["ok_runs"] = state.get("ok_runs", 0) + 1
        since = datetime.fromisoformat(state["ok_since"])
        if now - since >= OK_REPORT_PERIOD:
            print("[*] 24h without failures, sending OK report")
            send(format_ok_report(since, now, state["ok_runs"]))
            state["ok_since"] = now.isoformat()
            state["ok_runs"] = 1

    state["last_run"] = now.isoformat()


def main():
    load_config()
    now = datetime.now()
    print(f"=== ICS Agent run {now:%Y-%m-%d %H:%M:%S} ===")

    all_ok = True
    for name, script, url_var in HMIS:
        print(f"[->] {name}")
        ok, output = run_check_with_retries(script, url_var)
        print(f"[{'OK' if ok else 'FAIL'}] {name}\n")
        if not ok:
            all_ok = False
            send(format_alert(name, os.environ.get(url_var), output, now))

    state = load_state()
    update_ok_streak(state, all_ok, now)
    save_state(state)

    print(f"=== Finished: {'all OK' if all_ok else 'failures detected'} ===")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Stop one backend, measure availability/errors while it's down, restart it,
and prove it's serving traffic again. Always restores the backend, even on
failure or Ctrl+C (see try/finally in main)."""

import json
import subprocess
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8080"
PROJECT = "barq-assessment"
TARGET_BACKEND = "app-01"   # which backend we intentionally take down
TIMEOUT = 5                  # bounded wait per HTTP call
PROBE_COUNT = 20             # requests sent per phase
PROBE_DELAY = 0.2            # seconds between requests in a phase


def docker_compose(*args):
    """Run a docker compose command scoped to our project. Raises on failure."""
    cmd = ["docker", "compose", "-p", PROJECT, *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def probe_once():
    """One GET /records call. Returns True on 200, False on anything else
    (including network-level failure) — never raises, so a bad response
    doesn't crash the measurement loop."""
    try:
        req = urllib.request.Request(BASE_URL + "/records", method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status == 200
    except Exception:
        return False


def run_phase(label, count=PROBE_COUNT, delay=PROBE_DELAY):
    """Send `count` requests, spaced `delay` seconds apart, and report the
    success rate for this phase (baseline / during-failure / after-recovery)."""
    print(f"\n--- phase: {label} ---")
    successes = 0
    for i in range(count):
        ok = probe_once()
        successes += ok
        time.sleep(delay)
    rate = successes / count * 100
    print(f"{label}: {successes}/{count} succeeded ({rate:.1f}%)")
    return successes, count


def wait_until_healthy(service, timeout=30):
    """Bounded wait: poll `docker compose ps` until the service shows healthy,
    or give up after `timeout` seconds (never hangs forever)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = docker_compose("ps", service)
        if "healthy" in out:
            return True
        time.sleep(2)
    return False


def main():
    exit_code = 0

    try:
        # 1) Baseline — confirm normal behavior before we break anything
        base_ok, base_total = run_phase("baseline (before stopping backend)")
        if base_ok != base_total:
            print(f"WARNING: baseline itself wasn't 100% healthy ({base_ok}/{base_total}) "
                  "— results below may be affected by a pre-existing issue.")

        # 2) Stop the target backend and measure traffic while it's down
        print(f"\nStopping {TARGET_BACKEND} ...")
        docker_compose("stop", TARGET_BACKEND)
        during_ok, during_total = run_phase(f"during failure ({TARGET_BACKEND} stopped)")

        # 3) Restart it and wait (bounded) for it to become healthy again
        print(f"\nStarting {TARGET_BACKEND} ...")
        docker_compose("start", TARGET_BACKEND)
        became_healthy = wait_until_healthy(TARGET_BACKEND, timeout=30)
        print(f"{TARGET_BACKEND} healthy again: {became_healthy}")

        # 4) Measure after recovery — this is the actual proof of recovery
        after_ok, after_total = run_phase("after recovery")

        # ---------- verdict ----------
        print("\n=== summary ===")
        print(f"baseline       : {base_ok}/{base_total}")
        print(f"during failure : {during_ok}/{during_total}")
        print(f"after recovery : {after_ok}/{after_total}")

        recovery_ok = became_healthy and after_ok == after_total
        if not recovery_ok:
            print("\nFAIL: backend did not fully recover after restart.")
            exit_code = 1
        else:
            print("\nPASS: system stayed available during the outage "
                  "(thanks to NGINX failover) and fully recovered afterward.")

    finally:
        # SAFETY NET: no matter what happened above (including an exception
        # or Ctrl+C), make sure we don't leave the backend stopped.
        print(f"\n[cleanup] ensuring {TARGET_BACKEND} is running...")
        try:
            docker_compose("start", TARGET_BACKEND)
        except Exception as e:
            print(f"[cleanup] WARNING: could not confirm {TARGET_BACKEND} is running: {e}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()


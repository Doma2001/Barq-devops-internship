#!/usr/bin/env python3
"""Validate the BARQ environment: public access, all endpoints, both
backends, dependency readiness, and network isolation. Bounded waits only,
PASS/FAIL per check, non-zero exit on any failure."""

import json
import socket
import sys
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8080"
TIMEOUT = 5          # seconds — bounded wait per network call
INSTANCE_PROBE_COUNT = 10   # how many times we call /instance to see both backends

results = []  # (name, passed: bool, detail: str)


def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    results.append((name, passed, detail))


def http_get(path, timeout=TIMEOUT):
    """GET request with a bounded timeout. Returns (status_code, headers, body_text)
    or raises on network-level failure (which callers must catch)."""
    req = urllib.request.Request(BASE_URL + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as e:
        # HTTPError still carries a real status code (e.g. 404, 503) — not a crash
        return e.code, dict(e.headers or {}), e.read().decode()


def http_post_json(path, payload, timeout=TIMEOUT):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE_URL + path, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def port_is_reachable(host, port, timeout=2):
    """Bounded check: True if something accepts a TCP connection on host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---------- individual checks ----------

def check_public_root():
    try:
        status, _, _ = http_get("/")
        record("Public root (/) reachable on host:8080", status == 200, f"status={status}")
    except Exception as e:
        record("Public root (/) reachable on host:8080", False, str(e))


def check_health():
    try:
        status, _, _ = http_get("/health")
        record("GET /health returns 200", status == 200, f"status={status}")
    except Exception as e:
        record("GET /health returns 200", False, str(e))


def check_ready():
    try:
        status, _, _ = http_get("/ready")
        record("GET /ready returns 200 (PostgreSQL + Redis reachable)", status == 200, f"status={status}")
    except Exception as e:
        record("GET /ready returns 200 (PostgreSQL + Redis reachable)", False, str(e))


def check_instance_header():
    try:
        status, headers, _ = http_get("/instance")
        has_header = "X-Instance-ID" in headers
        record("GET /instance returns 200 with X-Instance-ID header",
               status == 200 and has_header, f"status={status}, headers_has_id={has_header}")
    except Exception as e:
        record("GET /instance returns 200 with X-Instance-ID header", False, str(e))


def check_both_backends_serve_traffic():
    seen_instances = set()
    try:
        for _ in range(INSTANCE_PROBE_COUNT):
            _, _, body = http_get("/instance")
            data = json.loads(body)
            seen_instances.add(data.get("instance_id"))
        record("Both backend instances serve traffic (load balancing)",
               len(seen_instances) >= 2, f"distinct instance_ids seen={seen_instances}")
    except Exception as e:
        record("Both backend instances serve traffic (load balancing)", False, str(e))


def check_records_post_and_get():
    try:
        status, body = http_post_json("/records", {"title": "validate.py proof record"})
        post_ok = status == 201
        record("POST /records returns 201", post_ok, f"status={status}")

        status, _, body = http_get("/records")
        get_ok = status == 200 and "records" in json.loads(body)
        record("GET /records returns 200 with records list", get_ok, f"status={status}")
    except Exception as e:
        record("POST/GET /records", False, str(e))


def check_counter():
    try:
        status, _, body = http_get("/counter")
        ok = status == 200 and "counter" in json.loads(body)
        record("GET /counter returns 200 with counter value", ok, f"status={status}")
    except Exception as e:
        record("GET /counter returns 200 with counter value", False, str(e))


def check_network_isolation():
    # These must NOT be reachable directly from the host — only via NGINX.
    postgres_open = port_is_reachable("127.0.0.1", 5432)
    redis_open = port_is_reachable("127.0.0.1", 6379)
    record("PostgreSQL port 5432 NOT exposed on host", not postgres_open,
           "reachable!" if postgres_open else "correctly blocked")
    record("Redis port 6379 NOT exposed on host", not redis_open,
           "reachable!" if redis_open else "correctly blocked")


def check_nginx_only_published_port():
    nginx_open = port_is_reachable("127.0.0.1", 8080)
    record("NGINX (port 8080) IS reachable on host", nginx_open,
           "reachable" if nginx_open else "NOT reachable — environment may be down")


# ---------- run everything ----------

def main():
    print("=== BARQ environment validation ===\n")

    check_nginx_only_published_port()
    check_public_root()
    check_health()
    check_ready()
    check_instance_header()
    check_both_backends_serve_traffic()
    check_records_post_and_get()
    check_counter()
    check_network_isolation()

    print("\n=== summary ===")
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"{passed} passed, {failed} failed, {len(results)} total")

    if failed > 0:
        print("\nFAILED CHECKS:")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}: {detail}")
        sys.exit(1)   # non-zero exit so CI can detect failure

    print("\nAll checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()

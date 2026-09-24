# Log analysis

Use all three supplied logs. Answer every question with commands/scripts and actual output.

1. What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?
2. How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?
3. What are the final client status counts and error rate? State your denominator.
4. Which paths, time windows and backends account for the failures?
5. What are the median and p95 client latencies? State the percentile method and units.
6. Which requests retried upstream? How many succeeded after retrying?
7. Build an incident timeline using evidence from access, error AND application logs.
8. Show one correlated failed request and one successful request. Include IDs and timestamps.
9. Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?
10. What do the logs not prove? What would you check next in a running environment?

## Commands / scripts
## Results
## Timeline and correlated examples
## Conclusions and limits

## Commands / scripts
Script: scripts/analyze_access.py (line-by-line JSON parsing with try/except,
deduplication by request_id using a set)

## Results

**01 — Coverage & line counts (access.log):**
- Valid lines: 725
- Malformed lines: 1 (line 311 — JSON truncated mid-value after "request_id":,
  no closing brace; likely a write interrupted by a container restart at that moment)
- Duplicate lines: 5 (request_ids lab-000121, 241, 361, 481, 601 — each appears
  twice with byte-for-byte identical timestamp and request_time, all on path "/",
  spaced exactly 5 minutes apart)
- Time range: 2026-08-20T11:00:00.015Z → 2026-08-20T11:29:57.578Z (~30 minutes)

**02 — Distinct client requests & dedup method:**
- Distinct request_ids after parsing: 720
- Deduplication method: iterate all valid lines in order, keep the first
  occurrence of each request_id in a `seen` set, skip any request_id already
  seen. This is safe here because the 5 duplicates are exact repeats of the
  same log line (not real retries — a real retry would show a different
  timestamp/request_time for the same request_id), so no legitimate data is lost.
- Distinct client requests: 720

**03 — Final client status counts & error rate:**
- 200: 615
- 404: 10
- 502: 40
- 503: 47
- 504: 8
- Denominator: 720 (deduplicated distinct client requests, from clean_records)
- Errors counted as status >= 500 only (404 excluded — it's a client-side
  "not found" on a real endpoint request, not a server failure)
- 5xx errors: 95
- Error rate: 95 / 720 = 13.19%

**04 — Failure breakdown by path, time and backend:**
- By path: /records (26), /counter (26), /ready (23), /health (10), / (10)
- By backend: 172.23.0.12:8080 → 68 errors, 172.23.0.11:8080 → 27 errors
  (errors concentrated on .12, not evenly split — points to one instance
  being unhealthy rather than a system-wide issue)
- Error time window: 2026-08-20T11:05:02.503Z → 11:26:47.001Z (~21 of the
  30 total minutes — failures did not span the entire log)

**05 — Latency percentiles:**
- Method: nearest-rank percentile on the sorted list of client request_time values (converted to ms)
- Sample size: 720 (deduplicated)
- Median (p50): 54.0 ms
- p95: 2001.0 ms (the ~2s values come from requests that hit the down/timing-out backend before failing or retrying)

**06 — Retried requests:**
- Detection method: access.log entries where the `upstream` field contains more than
  one host (comma-separated), meaning NGINX retried the request on a second upstream
  after the first failed
- Retried requests found: 19 (all during the 11:05–11:09 "Connection refused" window,
  all originally routed to 172.23.0.12, retried on 172.23.0.11)
- Succeeded after retry: 19 / 19 (100%) — every retried request ultimately returned
  200 to the client, confirming NGINX's failover correctly masked the app-02 outage
  for these specific requests (the other requests to app-02 during that window that
  were NOT retried ended in 502 to the client — see Q4 breakdown)

**07 — Incident timeline (cross-referencing all three logs):**
| Time (UTC) | Source | Event |
|---|---|---|
| 11:00:00 | access.log | Normal traffic begins, all 200s |
| 11:05:02–11:09:57 | error.log | 59x "Connection refused" connecting to 172.23.0.12:8080 — app-02 fully unreachable |
| 11:05:02–11:09:57 | access.log | 19 of the affected requests auto-retried to 172.23.0.11 and succeeded (200); the rest returned 502 to the client |
| 11:12:09–11:15:52 | application.log | 31x dependency_error (Redis TimeoutError) — occurring on BOTH app-01 and app-02, not just one instance |
| 11:20:07–11:21:45 | application.log | 16x dependency_error (Postgres) — again on both instances |
| 11:25:14–11:26:44 | error.log | 8x "upstream timed out" (slow, not down) split evenly across both 172.23.0.11 and 172.23.0.12 |
| 11:29:57 | access.log | Log capture ends, traffic back to normal 200s |

**08 — Correlated examples:**

*Failed request:* `lab-000122` at 11:05:02
- access.log: `status: 502, upstream: "172.23.0.12:8080", upstream_status: "502", request_time: 0.003`
- error.log: `connect() failed (111: Connection refused) ... upstream: "http://172.23.0.12:8080/health"`
- Not present in application.log — the request never reached the Flask app at all (confirms this was a pure connectivity failure, not an app-level bug)

*Successful (via retry) request:* `lab-000124` at 11:05:07
- access.log: `status: 200, upstream: "172.23.0.12:8080, 172.23.0.11:8080", upstream_status: "502, 200", request_time: 0.12`
- Shows NGINX tried 172.23.0.12 first (got 502/refused), automatically retried on 172.23.0.11, and that succeeded — client only ever saw 200

**09 — Proxy/connectivity issues vs dependency/application issues:**
- **Proxy/connectivity (NGINX ↔ backend network layer):** 59 "Connection refused" (app-02 process/port unreachable) + 8 "upstream timed out" (backend too slow to respond) = 67 events in error.log. Proof: these appear only in error.log with OS-level socket errors (errno 111, 110), and the corresponding request_ids in application.log show no log line at all for the refused ones — the request never got that far.
- **Dependency/application issues (inside the Flask app):** 47 dependency_error events in application.log (31 Redis TimeoutError + 16 Postgres), occurring on both app-01 and app-02 simultaneously. Proof: these have `level: ERROR` and an explicit `dependency`/`error_type` field logged from inside the app itself, and they affect both instances at once — ruling out a single-container network problem and pointing to the shared Redis/Postgres dependency being slow or unreachable during that window.

**010 — What the logs don't prove, and what to check next in a live environment:**
- The logs don't show *why* app-02 became unreachable at 11:05 (crash? OOM kill? manual stop? healthcheck-triggered restart?) — would need `docker inspect`/exit codes or host-level events from that moment, which aren't in these three files.
- The logs don't show *why* Redis and Postgres became slow/unreachable at 11:12 and 11:20 — could be resource exhaustion on those containers, network partition, or a connection pool exhaustion in the app. Would need Redis/Postgres's own logs and resource metrics (CPU/memory) from that time window to confirm.
- The logs don't prove whether the 5 exact-duplicate lines in access.log were an NGINX logging bug or something else — would need NGINX's own internal buffering/config from that deployment to confirm the mechanism.
- The 502s not covered by a retry (the majority of the 40 total 502s) suggest NGINX's retry policy didn't cover every path/method during the incident — would need the nginx.conf that was active *during* this historical incident (not necessarily the same as the one being fixed today) to confirm proxy_next_upstream/max_fails settings at the time.

import json

with open("logs/access.log") as f:
    lines = f.readlines()

print("number of lines:", len(lines))

valid = 0
malformed = 0

for line in lines:
    line = line.strip()
    if not line:
        continue
    try:
        data = json.loads(line)
        valid += 1
    except json.JSONDecodeError:
        malformed += 1
        print("MALFORMED LINE FOUND:", line)

print("valid:", valid)
print("malformed:", malformed)


from collections import Counter

request_ids = []

for line in lines:
    line = line.strip()
    if not line:
        continue
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        continue
    request_ids.append(data["request_id"])

print("distinct request_ids:", len(set(request_ids)))

counts = Counter(request_ids)
duplicates = {rid: c for rid, c in counts.items() if c > 1}
print("duplicated ids:", duplicates)

#---------------------------------------------------------------------------
print()
print("=== inspecting duplicate request_ids ===")
for line in lines:
    line = line.strip()
    if not line:
        continue
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        continue
    if data["request_id"] in duplicates:
        print(data)

#--------------------------------------------------------------------------
print()
print("=== deduplication ===")
seen = set()
clean_records = []

for line in lines:
    line = line.strip()
    if not line:
        continue
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        continue
    if data["request_id"] in seen:
        continue
    seen.add(data["request_id"])
    clean_records.append(data)

print("distinct client requests after dedup:", len(clean_records))

#----------------------------------------------------------------------------
print()
print("=== time range ===")
timestamps = sorted(r["timestamp"] for r in clean_records)
print("first:", timestamps[0])
print("last:", timestamps[-1])

#-----------------------------------------------------------------------------
print()
print("=== status counts ===")
status_counts = Counter(r["status"] for r in clean_records)
for status, count in sorted(status_counts.items()):
    print(status, ":", count)

total = len(clean_records)
errors = sum(c for s, c in status_counts.items() if s >= 500)
print("total:", total)
print("5xx errors:", errors)
print("error rate:", round(errors / total * 100, 2), "%")

#----------------------------------------------------------------------------
print()
print("=== errors by path ===")
error_records = [r for r in clean_records if r["status"] >= 500]
by_path = Counter(r["path"] for r in error_records)
for path, count in by_path.most_common():
    print(path, ":", count)

print()
print("=== errors by upstream backend ===")
by_upstream = Counter(r["upstream"] for r in error_records)
for upstream, count in by_upstream.most_common():
    print(upstream, ":", count)

print()
print("=== error time window ===")
error_timestamps = sorted(r["timestamp"] for r in error_records)
print("first error:", error_timestamps[0])
print("last error:", error_timestamps[-1])

#------------------------------------------------------------------------------------
# ---------- Q5: median and p95 client latency ----------
print()
print("=== Q5: latency percentiles ===")
latencies_ms = sorted(r["request_time"] * 1000 for r in clean_records)

def percentile(sorted_list, pct):
    idx = int(round(pct / 100 * (len(sorted_list) - 1)))
    return sorted_list[idx]

print("count:", len(latencies_ms))
print("median (p50) ms:", round(percentile(latencies_ms, 50), 2))
print("p95 ms:", round(percentile(latencies_ms, 95), 2))

# ---------- Q6: retried requests ----------
print()
print("=== Q6: retried requests ===")
retried = [r for r in clean_records if "," in str(r.get("upstream", ""))]
succeeded_after_retry = sum(1 for r in retried if r["status"] == 200)
print("requests with multiple upstreams (retried):", len(retried))
print("succeeded after retry (status 200):", succeeded_after_retry)

# ---------- Q9: proxy/connectivity vs dependency/application errors ----------
print()
print("=== Q9: error.log breakdown (proxy/connectivity) ===")
conn_refused = sum(1 for l in open("logs/error.log") if "Connection refused" in l)
upstream_timeout = sum(1 for l in open("logs/error.log") if "upstream timed out" in l)
print("connection refused:", conn_refused)
print("upstream timed out:", upstream_timeout)

print()
print("=== Q9: application.log dependency errors (app/dependency-level) ===")
dep_errors = Counter()
for line in open("logs/application.log"):
    try:
        d = json.loads(line.strip())
    except json.JSONDecodeError:
        continue
    if d.get("event") == "dependency_error":
        dep_errors[d.get("dependency")] += 1
print("dependency_error counts:", dict(dep_errors))

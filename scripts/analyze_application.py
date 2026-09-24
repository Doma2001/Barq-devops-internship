import json
from collections import Counter

with open("logs/application.log") as f:
    lines = f.readlines()

valid = 0
malformed = 0
records = []

for line in lines:
    line = line.strip()
    if not line:
        continue
    try:
        data = json.loads(line)
        valid += 1
        records.append(data)
    except json.JSONDecodeError:
        malformed += 1
        print("MALFORMED:", line)

print("total lines:", len(lines))
print("valid:", valid)
print("malformed:", malformed)


key_counts = Counter((r["request_id"], r["event"]) for r in records if r.get("request_id"))
true_duplicates = {k: v for k, v in key_counts.items() if v > 1}
print("true duplicate (same request_id + same event twice):", true_duplicates)

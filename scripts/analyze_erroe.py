import re
from collections import Counter

with open("logs/error.log") as f:
    lines = f.readlines()

error_lines = []
non_error_lines = []
malformed = []

pattern = re.compile(r"request_id=([a-zA-Z0-9\-]+)")

for line in lines:
    line = line.strip()
    if not line:
        continue
    if "[error]" not in line:
        non_error_lines.append(line)
        continue
    match = pattern.search(line)
    if match:
        error_lines.append((match.group(1), line))
    else:
        malformed.append(line)

print("total lines:", len(lines))
print("error lines (with request_id):", len(error_lines))
print("non-error lines (e.g. [notice]):", non_error_lines)
print("malformed [error] lines (missing request_id):", malformed)


ids = Counter(rid for rid, _ in error_lines)
dups = {rid: c for rid, c in ids.items() if c > 1}
print("duplicate request_ids in error.log:", dups)

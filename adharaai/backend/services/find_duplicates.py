"""
find_duplicates.py — locates exact line ranges of duplicate rule dicts
in risk_flagger.py, so you know precisely what to delete.

Run from your project root:
    python find_duplicates.py
"""

import re
from collections import defaultdict

PATH = "backend/services/risk_flagger.py"

with open(PATH, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find each "id": "..." line along with its line number
id_pattern = re.compile(r'"id":\s*"([^"]+)"')
occurrences = defaultdict(list)

for lineno, line in enumerate(lines, start=1):
    m = id_pattern.search(line)
    if m:
        occurrences[m.group(1)].append(lineno)

dupes = {rule_id: locs for rule_id, locs in occurrences.items() if len(locs) > 1}

total_ids = sum(len(v) for v in occurrences.values())
print(f"Total rule entries found: {total_ids}")
print(f"Unique rule IDs: {len(occurrences)}")
print()

if not dupes:
    print("No duplicates found. File looks clean.")
else:
    print(f"Duplicated rule IDs ({len(dupes)}):\n")
    for rule_id, locs in dupes.items():
        print(f"  '{rule_id}' appears at lines: {locs}")

    print()
    print("To inspect a duplicate block in context, e.g. for the first one:")
    first_id, first_locs = next(iter(dupes.items()))
    print(f"  Get-Content {PATH} | Select-Object -Index ({first_locs[-1]-3}..{first_locs[-1]+15})")
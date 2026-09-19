import re
import shutil

RISK_FLAGGER_PATH = "backend/services/risk_flagger.py"
NEW_RULES_PATH = "new_rules_batch.py"
BACKUP_PATH = "backend/services/risk_flagger.py.bak2"

with open(RISK_FLAGGER_PATH, "r", encoding="utf-8") as f:
    main_text = f.read()

with open(NEW_RULES_PATH, "r", encoding="utf-8") as f:
    new_rules_text = f.read()

shutil.copy(RISK_FLAGGER_PATH, BACKUP_PATH)
print(f"Backup saved to {BACKUP_PATH}")

existing_ids = set(re.findall(r'"id":\s*"([^"]+)"', main_text))
new_ids = re.findall(r'"id":\s*"([^"]+)"', new_rules_text)

clashes = [rid for rid in new_ids if rid in existing_ids]
if clashes:
    print(f"WARNING: these IDs already exist and were skipped: {clashes}")

dupes_within_new = [rid for rid in set(new_ids) if new_ids.count(rid) > 1]
if dupes_within_new:
    print(f"WARNING: these IDs appear more than once within new_rules_batch.py: {dupes_within_new}")

match = re.search(r"(RULES\s*=\s*\[)(.*?)(\n\]\s*\n)", main_text, re.DOTALL)
if not match:
    raise SystemExit("Could not locate RULES = [ ... ] block — aborting, no changes made.")

before_close = match.start(3)

blocks = re.split(r"\n(?=\s*\{\s*\n\s*\"id\")", new_rules_text)
blocks_to_insert = []
for block in blocks:
    m = re.search(r'"id":\s*"([^"]+)"', block)
    if not m:
        continue
    if m.group(1) in existing_ids:
        continue
    blocks_to_insert.append(block.rstrip())
    existing_ids.add(m.group(1))

insertion_text = "\n\n" + "\n\n".join(blocks_to_insert) + "\n"

new_text = main_text[:before_close] + insertion_text + main_text[before_close:]

with open(RISK_FLAGGER_PATH, "w", encoding="utf-8") as f:
    f.write(new_text)

print(f"Inserted {len(blocks_to_insert)} new rule blocks.")
print(f"{RISK_FLAGGER_PATH} has been updated.")
print()
print("Verify with:")
print('  python -c "from backend.services.risk_flagger import RULES; print(len(RULES))"')
print(f"If anything looks wrong, restore from backup: {BACKUP_PATH}")

"""
apply_rule_fixes.py

Run this once from your project root:
    python apply_rule_fixes.py

Fixes two rules in backend/services/risk_flagger.py:

1. admission_of_liability -- was too broad, firing on normal clauses like
   "Tenant shall accept responsibility for damages caused by them."
   Now requires nearby dispute/claim context and excludes routine liability
   acceptance language.

2. excessive_deposit -- was firing on ANY deposit clause with a number,
   even a standard 2-month deposit. Now only fires on deposits of 3+
   months, using normalize_numbers() so it also catches spelled-out
   amounts like "three months".

Safe to run multiple times -- checks if already patched first.
"""

PATH = "backend/services/risk_flagger.py"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

changed = False

# ── Fix 1: admission_of_liability ──────────────────────────────────────────
old_rule_1 = '''    {
        "id": "admission_of_liability",
        "pattern": r"(admit|acknowledge|accept).{0,60}(liability|guilt|fault|responsibility).{0,60}(without\\s+prejudice)?",
        "level": "high",
        "reason": "This document may contain language where you admit liability or fault — this can be used against you later.",
        "tip": "Do not sign any document admitting fault or liability without a lawyer reviewing it first.",
        "confidence": 82,
        "requires_not": [r"deny|dispute|without\\s+admitting"],
    },'''

new_rule_1 = '''    {
        "id": "admission_of_liability",
        "pattern": r"(admit|acknowledge|accept).{0,40}(liability|guilt|fault).{0,60}(claim|dispute|proceeding|court|lawsuit|allegation)",
        "level": "high",
        "reason": "This document may contain language where you admit liability or fault in a dispute — this can be used against you later.",
        "tip": "Do not sign any document admitting fault or liability without a lawyer reviewing it first.",
        "confidence": 82,
        "requires_not": [r"deny|dispute\\s+the|without\\s+admitting|for\\s+damages\\s+caused\\s+by\\s+them"],
    },'''

if old_rule_1 in content:
    content = content.replace(old_rule_1, new_rule_1, 1)
    changed = True
    print("Fixed: admission_of_liability (narrowed to require dispute/claim context)")
elif '"id": "admission_of_liability"' not in content:
    print("Skipped: admission_of_liability rule not found (may already be modified)")
else:
    print("Skipped: admission_of_liability found but text didn't match exactly -- may need manual review")

# ── Fix 2: excessive_deposit ────────────────────────────────────────────────
old_rule_2 = '''    {
        "id": "excessive_deposit",
        "pattern": r"(security|advance)\\s+deposit.{0,80}(rs\\.?\\s*[\\d,]+|rupees).{0,20}(month|months)",
        "level": "medium",
        "reason": "Verify this deposit amount. Most states cap security deposits at 2–3 months' rent.",
        "tip": "Check your state's Rent Control Act for the maximum permissible security deposit.",
        "confidence": 70,
        "requires_not": []
    },'''

new_rule_2 = '''    {
        "id": "excessive_deposit",
        "pattern": r"(security|advance)\\s+deposit.{0,80}([3-9]|[1-9]\\d+)\\s*(month|months)",
        "level": "medium",
        "reason": "This security deposit is 3 or more months' rent. Most states cap security deposits at 2 months.",
        "tip": "Check your state's Rent Control Act for the maximum permissible security deposit.",
        "confidence": 74,
        "requires_not": [r"two\\s+months?|1\\s+month|one\\s+month"]
    },'''

if old_rule_2 in content:
    content = content.replace(old_rule_2, new_rule_2, 1)
    changed = True
    print("Fixed: excessive_deposit (now only fires on 3+ months, not any deposit)")
elif '"id": "excessive_deposit"' not in content:
    print("Skipped: excessive_deposit rule not found (may already be modified)")
else:
    print("Skipped: excessive_deposit found but text didn't match exactly -- may need manual review")

if changed:
    with open(PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("\\nFile saved.")
else:
    print("\\nNo changes made.")
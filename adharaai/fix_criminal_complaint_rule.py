"""
fix_criminal_complaint_rule.py

Run once from your project root:
    python fix_criminal_complaint_rule.py

Fixes criminal_complaint_notice, which required its two keyword groups
to appear in a strict order (trigger word THEN summon/notice/appear).
Real text often has them in reverse order ("summoned to appear... FIR
No. 245/2026... police station"), so the rule silently failed to match.

Switches to lookaheds so both terms can appear in either order.
"""

PATH = "backend/services/risk_flagger.py"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

old = r'"pattern": r"(criminal\s+complaint|\bfir\b|cognizable\s+offence|police\s+station).{0,100}(summon|notice|appear)",'
new = r'"pattern": r"(?=.{0,200}(criminal\s+complaint|\bfir\b|cognizable\s+offence|police\s+station))(?=.{0,200}(summon|notice|appear))",'

if new in content:
    print("Already patched. No changes made.")
elif old not in content:
    raise SystemExit(
        "Could not find the exact criminal_complaint_notice pattern line. "
        "It may have already been edited manually -- check the rule directly."
    )
else:
    content = content.replace(old, new, 1)
    with open(PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed: criminal_complaint_notice now matches regardless of keyword order.")
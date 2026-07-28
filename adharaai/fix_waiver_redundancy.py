"""
fix_waiver_redundancy.py

Run once from your project root:
    python fix_waiver_redundancy.py

waiver_of_legal_rights and waiver_all_courts can both fire on the same
clause when it mentions both "waive" and specific court names (e.g.
"Tenant waives the right to approach any consumer court"). Since
waiver_all_courts is more specific (names actual court types) and has
higher confidence, this patch excludes waiver_of_legal_rights from
firing when that more specific court-list language is present --
avoiding duplicate-feeling entries in all_flags for the same underlying
risk.
"""

PATH = "backend/services/risk_flagger.py"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

old = '''    {
        "id": "waiver_of_legal_rights",
        "pattern": r"waive[sd]?.{0,80}(legal\\s+action|court|proceedings|sue|claim|dispute|remedy|statutory)",  # broader
        "level": "high",
        "reason": "You are being asked to give up your legal rights to take action.",
        "tip": "Many statutory rights cannot be waived under Indian law. Have a lawyer review this before signing.",
        "confidence": 93,
        "requires_not": []
    },'''

new = '''    {
        "id": "waiver_of_legal_rights",
        "pattern": r"waive[sd]?.{0,80}(legal\\s+action|court|proceedings|sue|claim|dispute|remedy|statutory)",  # broader
        "level": "high",
        "reason": "You are being asked to give up your legal rights to take action.",
        "tip": "Many statutory rights cannot be waived under Indian law. Have a lawyer review this before signing.",
        "confidence": 93,
        # Excludes cases already caught more specifically by waiver_all_courts
        # (named court types), avoiding duplicate flags for the same clause.
        "requires_not": [r"consumer\\s+court|civil\\s+court|legal\\s+forum|any\\s+court|any\\s+forum|tribunal"]
    },'''

if new in content:
    print("Already patched. No changes made.")
elif old not in content:
    raise SystemExit(
        "Could not find the exact waiver_of_legal_rights rule text. "
        "It may have already been edited -- check the rule directly."
    )
else:
    content = content.replace(old, new, 1)
    with open(PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed: waiver_of_legal_rights now defers to waiver_all_courts when specific court names are present.")
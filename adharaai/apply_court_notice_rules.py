"""
apply_court_notice_rules.py

Run this once from your project root:
    python apply_court_notice_rules.py

Adds 5 new rules covering court notices, which were previously thin
(only 2 of 63 rules touched this despite it being a stated document
type the app supports):

  - non_appearance_consequence  : failing to appear risks ex-parte ruling
  - property_attachment_risk    : attachment/seizure of assets or bank accounts
  - arrest_warrant_mention      : notice references an arrest warrant
  - appeal_deadline_window      : strict deadline to appeal a judgment
  - criminal_complaint_notice   : notice relates to FIR/criminal complaint

Safe to run multiple times -- checks if already patched first.
"""

PATH = "backend/services/risk_flagger.py"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

if '"id": "non_appearance_consequence"' in content:
    print("Already patched -- court notice rules found. No changes made.")
    raise SystemExit(0)

anchor_id = '"id": "termination_without_reason"'
anchor_pos = content.find(anchor_id)
if anchor_pos == -1:
    raise SystemExit(
        "Could not find the anchor rule 'termination_without_reason' in the file. "
        "The RULES list may have been reordered -- insert the new rules manually."
    )

# Find the closing bracket of the RULES list, searching forward from the anchor
close_pos = content.find("\n]", anchor_pos)
if close_pos == -1:
    raise SystemExit(
        "Found the anchor rule but couldn't locate the closing ']' of the RULES list. "
        "Insert the new rules manually just before RULES = [ ... ] closes."
    )

NEW_RULES = '''
    # ── HIGH RISK: Court notices ────────────────────────────────────────────

    {
        "id": "non_appearance_consequence",
        "pattern": r"(fail(ure)?\\s+to\\s+appear|non[-\\s]?appearance).{0,100}(ex[-\\s]?parte|warrant|judgment|decree|proceed)",
        "level": "high",
        "reason": "If you don't appear in court as required, the case may proceed without you and a ruling could be made against you.",
        "tip": "Attend the hearing or send a lawyer on the specified date. Non-appearance can result in an unfavourable ruling without your side being heard.",
        "confidence": 90,
        "requires_not": [],
    },
    {
        "id": "property_attachment_risk",
        "pattern": r"(attach(ment)?|garnishee|seiz(e|ure)).{0,80}(propert(y|ies)|bank\\s+account|assets|salary)",
        "level": "high",
        "reason": "This notice mentions attachment or seizure of your property, bank accounts, or assets — a serious legal consequence.",
        "tip": "Consult a lawyer immediately. Attachment orders can freeze your assets before a final judgment is even reached.",
        "confidence": 89,
        "requires_not": [],
    },
    {
        "id": "arrest_warrant_mention",
        "pattern": r"(arrest\\s+warrant|non[-\\s]?bailable\\s+warrant|bailable\\s+warrant|warrant\\s+of\\s+arrest)",
        "level": "high",
        "reason": "This notice references an arrest warrant — a serious legal matter requiring immediate attention.",
        "tip": "Contact a criminal lawyer immediately. Do not ignore any notice mentioning an arrest warrant.",
        "confidence": 93,
        "requires_not": [],
    },
    {
        "id": "appeal_deadline_window",
        "pattern": r"(appeal|revision|review\\s+petition).{0,80}(within\\s+(\\d+)\\s+days|limitation\\s+period)",
        "level": "high",
        "reason": "There is a strict deadline to file an appeal against this order or judgment.",
        "tip": "Missing the appeal deadline generally forfeits your right to challenge the decision. Consult a lawyer immediately.",
        "confidence": 87,
        "requires_not": [],
    },
    {
        "id": "criminal_complaint_notice",
        "pattern": r"(criminal\\s+complaint|\\bfir\\b|cognizable\\s+offence|police\\s+station).{0,100}(summon|notice|appear)",
        "level": "high",
        "reason": "This notice relates to a criminal complaint or FIR — this requires more urgent legal attention than a typical civil matter.",
        "tip": "Consult a criminal lawyer as soon as possible; criminal matters have different procedures and stricter timelines than civil disputes.",
        "confidence": 88,
        "requires_not": [],
    },
'''

content = content[:close_pos] + NEW_RULES + content[close_pos:]

with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched successfully: added 5 new court notice rules.")
print("  - non_appearance_consequence")
print("  - property_attachment_risk")
print("  - arrest_warrant_mention")
print("  - appeal_deadline_window")
print("  - criminal_complaint_notice")
content = open('backend/services/risk_flagger.py', encoding='utf-8').read()

new_rules = """
    {
        "id": "subletting_ban_onerous",
        "pattern": r"(not|shall\\s+not|must\\s+not).{0,40}sublet.{0,80}(each\\s+(and\\s+every\\s+)?occasion|every\\s+instance|each\\s+time)",
        "level": "medium",
        "reason": "You need written permission every single time — this is unusually restrictive.",
        "tip": "Negotiate for a one-time permission or a reasonable subletting clause.",
        "confidence": 82,
        "requires_not": [],
    },
    {
        "id": "immediate_eviction_pet",
        "pattern": r"(no\\s+pets?|pets?\\s+prohibited|pets?\\s+not\\s+allowed).{0,120}(immediate\\s+eviction|eviction\\s+without\\s+notice)",
        "level": "high",
        "reason": "Having a pet could result in immediate eviction with no warning and no deposit refund.",
        "tip": "Ask for a warning period of at least 7 days before eviction for minor violations.",
        "confidence": 88,
        "requires_not": [],
    },
    {
        "id": "blanket_future_amendments",
        "pattern": r"(agree|consent).{0,80}future\\s+(amend|modif|change).{0,80}(without\\s+consent|deemed\\s+fit|discretion)",
        "level": "high",
        "reason": "You are agreeing in advance to any future changes the landlord makes without being asked.",
        "tip": "Remove this clause. All amendments must require written consent from both parties.",
        "confidence": 91,
        "requires_not": [],
    },
    {
        "id": "waiver_all_courts",
        "pattern": r"(shall\\s+not|must\\s+not|not\\s+entitled).{0,60}(consumer\\s+court|civil\\s+court|legal\\s+forum|any\\s+court|tribunal)",
        "level": "high",
        "reason": "You are giving up your right to approach any court for any dispute.",
        "tip": "This clause is likely unenforceable under Indian law. Consult a lawyer.",
        "confidence": 94,
        "requires_not": [],
    },
    {
        "id": "vacate_24_hours",
        "pattern": r"vacate.{0,60}24\\s*hours?.{0,60}(notice|receiving|landlord)",
        "level": "high",
        "reason": "You could be required to leave within just 24 hours of receiving notice.",
        "tip": "24 hours notice is likely illegal under Indian Rent Control Acts. Ask for 30 days minimum.",
        "confidence": 92,
        "requires_not": [],
    },
    {
        "id": "repair_request_delay",
        "pattern": r"(tenant|lessee).{0,60}(30|thirty)\\s+days?.{0,60}notice.{0,60}(maintenance|repair)",
        "level": "medium",
        "reason": "You must give 30 days advance notice before the landlord is required to fix anything.",
        "tip": "Negotiate for urgent repairs to be addressed within 48 hours without advance notice.",
        "confidence": 80,
        "requires_not": [],
    },
    {
        "id": "guest_restriction_every_occasion",
        "pattern": r"guests?\\s+(not\\s+)?permitted.{0,100}overnight.{0,100}(each\\s+occasion|prior\\s+written\\s+permission)",
        "level": "medium",
        "reason": "You need written permission from the landlord every time a guest stays overnight.",
        "tip": "Negotiate for guests to be allowed for up to 7 days without requiring permission.",
        "confidence": 78,
        "requires_not": [],
    },
    {
        "id": "all_charges_tenant_property_tax",
        "pattern": r"(tenant|lessee).{0,60}(pay|bear|responsible).{0,80}property\\s+tax",
        "level": "medium",
        "reason": "You are responsible for paying property tax — this is normally the landlord's obligation.",
        "tip": "Property tax is the landlord's legal responsibility. Ask for this clause to be removed.",
        "confidence": 83,
        "requires_not": [],
    },
    {
        "id": "binding_on_heirs_no_consent",
        "pattern": r"binding.{0,60}(legal\\s+heirs?|successors?).{0,60}without.{0,40}(further\\s+consent|any\\s+consent)",
        "level": "medium",
        "reason": "This agreement automatically applies to your family members without their consent.",
        "tip": "Ask for a clause stating the agreement is personal and ends when you vacate.",
        "confidence": 76,
        "requires_not": [],
    },
"""

# Find the closing bracket of the RULES list
marker = ']'
idx = content.rfind('\nRULES = [')
if idx == -1:
    print("ERROR: Could not find RULES list")
else:
    # Find the closing ] of RULES
    rules_end = content.find('\n]\n', idx)
    if rules_end == -1:
        print("ERROR: Could not find end of RULES list")
    else:
        content = content[:rules_end] + '\n' + new_rules + content[rules_end:]
        open('backend/services/risk_flagger.py', 'w', encoding='utf-8').write(content)
        print("SUCCESS — rules added")
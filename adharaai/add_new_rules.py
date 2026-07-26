content = open('backend/services/risk_flagger.py', encoding='utf-8').read()

new_rules = """
    {
        "id": "rent_escalation_uncapped",
        "pattern": r"rent.{0,80}(increas|escalat|rais|revis).{0,80}(at\\s+(his|her|its|the\\s+landlord.s)\\s+(sole\\s+)?discretion|without\\s+(prior\\s+)?notice|any\\s+time|anytime)",
        "level": "high",
        "reason": "The landlord can increase your rent at any time without limit or notice.",
        "tip": "Negotiate for a fixed annual increase cap — typically 5-10% per year with 30 days prior written notice.",
        "confidence": 88,
        "requires_not": [],
    },
    {
        "id": "inspection_frequency_excessive",
        "pattern": r"(landlord|owner|lessor).{0,60}(inspect|enter|visit).{0,60}(weekly|daily|twice\\s+a\\s+month|every\\s+(week|day|two\\s+weeks)|more\\s+than\\s+(once|one\\s+time)\\s+a\\s+month)",
        "level": "medium",
        "reason": "The landlord can inspect your property very frequently — this is unusually intrusive.",
        "tip": "Negotiate for inspections to be limited to once every 3 months with 24 hours written notice.",
        "confidence": 82,
        "requires_not": [],
    },
    {
        "id": "abandonment_clause_short",
        "pattern": r"(abandon|deemed\\s+to\\s+have\\s+vacated|treated\\s+as\\s+abandoned).{0,120}(\\d+\\s*days?|\\d+\\s*hours?)",
        "level": "high",
        "reason": "If you are absent for a short period, the landlord may treat the property as abandoned and repossess it.",
        "tip": "Ask for abandonment to be defined as absence of at least 30 days with no communication — not a shorter period.",
        "confidence": 85,
        "requires_not": [],
    },
    {
        "id": "personal_guarantee_demand",
        "pattern": r"(personal\\s+guarantee|guarantor|surety).{0,120}(jointly\\s+and\\s+severally|personally\\s+liable|unconditional)",
        "level": "high",
        "reason": "A third party is being asked to personally guarantee your obligations — making them liable for your debts.",
        "tip": "Ensure the guarantor understands their full financial exposure. Limit the guarantee to the deposit amount only if possible.",
        "confidence": 86,
        "requires_not": [],
    },
    {
        "id": "parking_rights_revocable",
        "pattern": r"(parking|car\\s+park).{0,100}(revok|withdraw|terminat|cancel|at\\s+(his|her|its|the)\\s+(sole\\s+)?discretion|without\\s+notice)",
        "level": "medium",
        "reason": "Your parking rights can be taken away at any time without notice or compensation.",
        "tip": "Ask for parking rights to be part of the core agreement — not a separate revocable licence.",
        "confidence": 78,
        "requires_not": [],
    },
    {
        "id": "subletting_profit_forfeiture",
        "pattern": r"(sublet|subletting|sub-let).{0,120}(profit|excess|surplus|additional\\s+rent).{0,80}(landlord|owner|lessor|shall\\s+belong|paid\\s+to)",
        "level": "high",
        "reason": "If you sublet the property, any profit above your rent must be paid to the landlord.",
        "tip": "This is unusual. If subletting is permitted, you should be entitled to keep the income from it.",
        "confidence": 83,
        "requires_not": [],
    },
    {
        "id": "training_bond_repayment",
        "pattern": r"(training|course|certification|programme).{0,120}(bond|repay|recover|deduct|clawback).{0,80}(resign|terminat|leav|quit|within\\s+\\d+\\s*(month|year))",
        "level": "high",
        "reason": "You may have to repay training costs if you leave the company within a certain period.",
        "tip": "Check the exact amount and time period. Ask for the bond to reduce proportionally the longer you stay.",
        "confidence": 87,
        "requires_not": [],
    },
    {
        "id": "data_sharing_employment",
        "pattern": r"(personal\\s+data|employee\\s+information|personal\\s+information).{0,120}(shar|transfer|disclos|provid).{0,80}(third\\s+part|affiliate|group\\s+compan|partner|client).{0,60}(without\\s+(your\\s+)?consent|at\\s+(our|the\\s+company.s)\\s+discretion)",
        "level": "medium",
        "reason": "Your personal data can be shared with third parties without your consent.",
        "tip": "Ask for data sharing to require your explicit written consent each time, in line with IT Act 2000 and DPDP Act 2023.",
        "confidence": 80,
        "requires_not": [],
    },
    {
        "id": "rent_free_period_clawback",
        "pattern": r"(rent.free|rent\\s+free|free\\s+period).{0,120}(clawback|recover|repay|deduct|forfeited?).{0,80}(terminat|vacate|leave|breach|default)",
        "level": "high",
        "reason": "Any rent-free period given to you must be repaid if you leave early or breach the agreement.",
        "tip": "Clarify exact conditions. Ask for the clawback to be proportional — not the full amount if you stay most of the term.",
        "confidence": 84,
        "requires_not": [],
    },
    {
        "id": "common_area_restriction",
        "pattern": r"(common\\s+area|common\\s+facilities|shared\\s+space|amenities).{0,100}(restrict|prohibit|not\\s+permitted|access\\s+may\\s+be.{0,30}(withdrawn|revoked|terminated))",
        "level": "medium",
        "reason": "Your access to common areas or shared facilities can be restricted or withdrawn.",
        "tip": "Access to common areas should be a right included in the rent — not a revocable privilege.",
        "confidence": 76,
        "requires_not": [],
    },
    {
        "id": "moonlighting_ban_absolute",
        "pattern": r"(not\\s+permitted|prohibited|shall\\s+not).{0,60}(engage|work|employed|consult|freelanc|moonlight).{0,80}(any\\s+other|outside|additional|other\\s+compan|third\\s+part)",
        "level": "medium",
        "reason": "You are completely banned from doing any outside work, freelancing, or consulting — even in your personal time.",
        "tip": "Many Indian employees do freelance work legally. Ask for the ban to be limited to competitors only, not all outside work.",
        "confidence": 79,
        "requires_not": [r"competitor|competing\\s+business|same\\s+industry"],
    },
    {
        "id": "termination_without_reason",
        "pattern": r"(terminat|dismiss|discharg|remov).{0,80}(without\\s+(assigning\\s+)?any\\s+reason|no\\s+reason|without\\s+cause|at\\s+will)",
        "level": "high",
        "reason": "You can be terminated at any time without any reason being given.",
        "tip": "Under Indian labour law, termination without cause may entitle you to compensation. Consult a lawyer if this happens.",
        "confidence": 91,
        "requires_not": [],
    },
"""

# Insert before closing ] of RULES list
marker = '\n]\n'
idx = content.rfind('\nRULES = [')
if idx == -1:
    print("ERROR: Could not find RULES list")
else:
    rules_end = content.find('\n]\n', idx)
    if rules_end == -1:
        print("ERROR: Could not find end of RULES list")
    else:
        content = content[:rules_end] + '\n' + new_rules + content[rules_end:]
        open('backend/services/risk_flagger.py', 'w', encoding='utf-8').write(content)
        print("SUCCESS — 12 new rules added")
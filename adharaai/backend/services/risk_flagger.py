"""
risk_flagger.py — High-accuracy Indian legal risk detection engine.

Architecture: 3-layer hybrid for >90% precision:
  Layer 1 — Exact keyword rules (high confidence, low false positives)
  Layer 2 — Pattern + context rules (medium confidence)
  Layer 3 — Structural rules (clause length, vague language detection)

Each rule has:
  - pattern     : regex (case-insensitive)
  - level       : "high" | "medium"
  - reason      : plain-English explanation
  - tip         : what the user should do
  - confidence  : 0-100 (how certain we are this is truly risky)
  - requires_not: optional list of patterns — if ANY match, skip this rule
                  (reduces false positives dramatically)
"""

import re
from typing import Optional

# ── Rule definitions ──────────────────────────────────────────────────────────

RULES = [

    # ── HIGH RISK: Termination ────────────────────────────────────────────────

    {
        "id": "unilateral_termination",
        "pattern": r"(landlord|owner|lessor|employer|company).{0,80}(terminat|cancel|evict|end|discontinue).{0,60}(without\s+notice|immediately|forthwith|at\s+(his|her|its|their)\s+(sole\s+)?discretion)",
        "level": "high",
        "reason": "The other party can terminate this agreement without giving you any notice.",
        "tip": "Negotiate for a minimum 30-day written notice period before termination.",
        "confidence": 92,
        "requires_not": [r"mutual\s+(consent|agreement)", r"both\s+parties"]
    },
    {
        "id": "no_notice_termination",
        "pattern": r"without\s+(prior\s+)?notice.{0,40}(terminat|vacate|leave|evict)",
        "level": "high",
        "reason": "This clause allows termination or eviction without any prior notice to you.",
        "tip": "Ask for at least 15–30 days written notice to be added explicitly.",
        "confidence": 90,
        "requires_not": [r"in\s+case\s+of\s+(default|breach|non[-\s]?payment)"]
    },
    {
        "id": "immediate_eviction",
        "pattern": r"(immediately|forthwith|at\s+once).{0,60}(vacate|leave|evict|remove)",
        "level": "high",
        "reason": "You could be required to vacate the premises immediately without time to arrange alternative accommodation.",
        "tip": "Negotiate for a minimum 7–15 days even in breach scenarios.",
        "confidence": 88,
        "requires_not": []
    },

    # ── HIGH RISK: Deposits ───────────────────────────────────────────────────

    {
        "id": "non_refundable_deposit",
        "pattern": r"non[-\s]?refundable",  # matches anywhere in clause
        "level": "high",
        "reason": "The security deposit is marked as non-refundable, which may not be fully enforceable in India.",
        "tip": "Under most Indian Rent Control Acts, security deposits must be refunded minus legitimate deductions. Ask for this clause to be removed.",
        "confidence": 95,
        "requires_not": [r"subject\s+to\s+deduction"]
    },
    {
        "id": "excessive_deposit",
        "pattern": r"(security|advance)\s+deposit.{0,80}(rs\.?\s*[\d,]+|rupees).{0,20}(month|months)",
        "level": "medium",
        "reason": "Verify this deposit amount. Most states cap security deposits at 2–3 months' rent.",
        "tip": "Check your state's Rent Control Act for the maximum permissible security deposit.",
        "confidence": 70,
        "requires_not": []
    },
    {
        "id": "deposit_forfeiture",
        "pattern": r"(deposit|advance).{0,60}(forfeit|forfeited|be\s+liable\s+to\s+forfeiture|stand\s+forfeited)",
        "level": "high",
        "reason": "The entire deposit can be forfeited — even for minor breaches.",
        "tip": "Forfeiture should be proportional to actual damage or loss. Ask for specific conditions and amounts.",
        "confidence": 88,
        "requires_not": []
    },

    # ── HIGH RISK: Lock-in ────────────────────────────────────────────────────

    {
        "id": "lockin_over_11_months",
        "pattern": r"lock.{0,5}in.{0,60}(1[2-9]|2\d|3\d)\s*(month|months)",
        "level": "high",
        "reason": "A lock-in period exceeding 11 months requires mandatory registration under the Registration Act 1908.",
        "tip": "Agreements longer than 11 months must be registered at the Sub-Registrar's office. Ensure this is done, or reduce the lock-in.",
        "confidence": 93,
        "requires_not": []
    },
    {
        "id": "lockin_penalty",
        "pattern": r"lock.{0,5}in.{0,120}(penalty|damages|liable|pay|deduct|forfeit)",
        "level": "high",
        "reason": "Leaving before the lock-in period ends may cost you a significant financial penalty.",
        "tip": "Clarify the exact penalty amount in writing. An unspecified penalty is difficult to predict or challenge.",
        "confidence": 85,
        "requires_not": []
    },

    # ── HIGH RISK: Penalty clauses ────────────────────────────────────────────

    {
        "id": "unlimited_penalty",
        "pattern": r"(penalty|damages|compensation).{0,60}(unlimited|without\s+limit|any\s+and\s+all\s+losses|all\s+losses)",
        "level": "high",
        "reason": "This clause creates unlimited financial liability for you.",
        "tip": "Negotiate a liability cap — typically limited to the contract value or a fixed amount.",
        "confidence": 91,
        "requires_not": []
    },
    {
        "id": "compound_penalty",
        "pattern": r"(penalty|interest).{0,80}(compound|compounding|per\s+day.{0,30}per\s+month|daily.{0,30}monthly)",
        "level": "high",
        "reason": "Compounding penalties can grow very rapidly and become unaffordable.",
        "tip": "Request a simple interest structure with a clear maximum cap.",
        "confidence": 87,
        "requires_not": []
    },
    {
        "id": "double_penalty",
        "pattern": r"(double|twice|triple|two\s+times?|2x).{0,60}(rent|penalty|amount|deposit)",  # fixed order
        "level": "high",
        "reason": "The penalty is set as a multiple of rent/amount — this may exceed what Indian courts would enforce.",
        "tip": "Under Section 74 of the Indian Contract Act, penalty must be a reasonable estimate of actual loss.",
        "confidence": 86,
        "requires_not": []
    },

    # ── HIGH RISK: Arbitration / Jurisdiction ─────────────────────────────────

    {
        "id": "foreign_arbitration",
        "pattern": r"arbitration.{0,80}(outside\s+india|foreign|international\s+arbitration\s+centre|london|singapore|dubai|new\s+york)",
        "level": "high",
        "reason": "Foreign arbitration is expensive, inconvenient, and may be difficult to enforce in India.",
        "tip": "Negotiate for arbitration in an Indian city under the Arbitration and Conciliation Act 1996.",
        "confidence": 94,
        "requires_not": []
    },
    {
        "id": "exclusive_jurisdiction_far",
        "pattern": r"(exclusive\s+jurisdiction|courts?\s+of).{0,80}(mumbai|delhi|bangalore|chennai|hyderabad|kolkata)",
        "level": "medium",
        "reason": "Legal disputes must be filed in a specific city, which may be inconvenient or expensive for you.",
        "tip": "Try to negotiate jurisdiction in your own city or the nearest major city.",
        "confidence": 72,
        "requires_not": []
    },

    # ── HIGH RISK: Indemnity ──────────────────────────────────────────────────

    {
        "id": "unlimited_indemnity",
        "pattern": r"indemnif(y|ication|ied).{0,120}(unlimited|without\s+limit|any\s+and\s+all|whatsoever|howsoever)",
        "level": "high",
        "reason": "You are agreeing to financially cover the other party for any and all losses — with no upper limit.",
        "tip": "Add a liability cap and carve out gross negligence / intentional misconduct from indemnity.",
        "confidence": 90,
        "requires_not": []
    },
    {
        "id": "third_party_indemnity",
        "pattern": r"indemnif(y|ication).{0,120}(third.{0,10}part(y|ies)|claims?\s+by\s+any\s+person|anyone)",
        "level": "medium",
        "reason": "You may be liable for claims made by people who are not even parties to this contract.",
        "tip": "Limit indemnity to direct losses between the contracting parties only.",
        "confidence": 78,
        "requires_not": []
    },

    # ── HIGH RISK: Waivers ────────────────────────────────────────────────────

    {
        "id": "waiver_of_legal_rights",
        "pattern": r"waive[sd]?.{0,80}(legal\s+action|court|proceedings|sue|claim|dispute|remedy|statutory)",  # broader
        "level": "high",
        "reason": "You are being asked to give up your legal rights to take action.",
        "tip": "Many statutory rights cannot be waived under Indian law. Have a lawyer review this before signing.",
        "confidence": 93,
        "requires_not": []
    },
    {
        "id": "waiver_of_rent_control",
        "pattern": r"waive[sd]?.{0,60}(rent\s+control|tenant\s+protection|rent\s+act)",
        "level": "high",
        "reason": "You may be waiving protection under the Rent Control Act — this waiver may not be legally valid.",
        "tip": "Rent Control Act protections generally cannot be waived by contract. Consult a lawyer.",
        "confidence": 91,
        "requires_not": []
    },

    # ── HIGH RISK: Auto-renewal ───────────────────────────────────────────────

    {
        "id": "auto_renewal_no_notice",
        "pattern": r"automatic(ally)?\s+renew(ed|al)?.{0,120}(unless.{0,60}notice|without\s+further\s+action|deemed\s+to\s+be\s+renewed)",
        "level": "high",
        "reason": "The contract renews automatically — you may be locked in for another term without realising it.",
        "tip": "Note the exact deadline to send a non-renewal notice and set a calendar reminder well in advance.",
        "confidence": 89,
        "requires_not": []
    },

    # ── HIGH RISK: Inspection / Entry ─────────────────────────────────────────

    {
        "id": "unrestricted_entry",
        "pattern": r"(landlord|owner|lessor|employer).{0,60}(enter|access|inspect).{0,60}(any\s+time|at\s+all\s+times|without\s+(prior\s+)?notice|at\s+(his|her|its)\s+(sole\s+)?discretion)",
        "level": "high",
        "reason": "The other party can enter your premises at any time without prior notice.",
        "tip": "Negotiate for at least 24-hour advance notice except in genuine emergencies.",
        "confidence": 88,
        "requires_not": [r"emergency|fire|flood|urgent\s+repair"]
    },

    # ── MEDIUM RISK: Vague / one-sided language ───────────────────────────────

    {
        "id": "sole_discretion",
        "pattern": r"(sole|absolute|unfettered|complete)\s+(discretion|authority|decision)",
        "level": "medium",
        "reason": "The other party has unchecked decision-making power with no obligation to be fair or reasonable.",
        "tip": "Add 'acting reasonably' or 'with written notice' to limit this power.",
        "confidence": 75,
        "requires_not": [r"mutual\s+(consent|agreement)"]
    },
    {
        "id": "as_may_be_required",
        "pattern": r"(such\s+other|any\s+other).{0,40}(obligations?|duties?|responsibilities?).{0,40}(as\s+may\s+be|as\s+(the|any)\s+(landlord|employer|company|party)\s+(may\s+)?deem)",
        "level": "medium",
        "reason": "This open-ended clause could be used to impose additional obligations on you without your consent.",
        "tip": "Ask for all obligations to be listed explicitly. Avoid agreeing to undefined future duties.",
        "confidence": 73,
        "requires_not": []
    },
    {
        "id": "unilateral_amendment",
        "pattern": r"(landlord|owner|employer|company).{0,60}(amend|modify|change|alter|vary).{0,60}(terms?|conditions?|agreement|contract).{0,60}(without|at\s+(his|her|its)\s+discretion|unilateral)",
        "level": "high",
        "reason": "The other party can change the terms of this agreement without your consent.",
        "tip": "All amendments should require written consent of both parties.",
        "confidence": 90,
        "requires_not": [r"written\s+consent\s+of\s+both"]
    },
    {
        "id": "stamp_duty_tenant",
        "pattern": r"stamp\s+duty.{0,60}(shall\s+be\s+(borne|paid|payable)\s+by\s+the\s+(tenant|lessee|employee)|entirely\s+by\s+the\s+(tenant|lessee))",
        "level": "medium",
        "reason": "Stamp duty is being placed entirely on you — typically it should be shared equally.",
        "tip": "Under most Indian state laws, stamp duty is shared equally between landlord and tenant.",
        "confidence": 80,
        "requires_not": [r"equally|shared|both\s+parties"]
    },
    {
        "id": "maintenance_tenant_all",
        "pattern": r"(all|entire|complete).{0,50}(maintenance|repair).{0,80}(tenant|lessee|borne\s+by\s+the\s+tenant)",  # fixed
        "level": "medium",
        "reason": "All maintenance costs are being placed on you — including costs that are typically the landlord's responsibility.",
        "tip": "Structural repairs and major maintenance should be the landlord's responsibility. Clarify exactly what you're responsible for.",
        "confidence": 77,
        "requires_not": [r"except\s+(structural|major|external)"]
    },
    {
        "id": "interest_on_delayed_rent",
        "pattern": r"interest.{0,60}(\d+\s*%|\d+\s*per\s*cent)",  # any interest with %
        "level": "medium",
        "reason": "Interest is charged on late rent — check whether the rate is reasonable.",
        "tip": "Interest above 12% per annum for consumer transactions may be considered excessive by Indian courts.",
        "confidence": 74,
        "requires_not": []
    },

    # ── ADDED BATCH: Rental fixes / additions ─────────────────────────────────

    {
        "id": "subletting_ban_onerous",
        "pattern": r"(not|shall\s+not|must\s+not).{0,40}sublet.{0,80}(each\s+(and\s+every\s+)?occasion|every\s+instance|each\s+time)",
        "level": "medium",
        "reason": "You need written permission every single time you want a subtenant — this is unusually restrictive.",
        "tip": "Negotiate for a one-time permission or a reasonable subletting clause with 30 days notice.",
        "confidence": 82,
        "requires_not": [],
    },
    {
        "id": "immediate_eviction_pet",
        "pattern": r"(no\s+pets?|pets?\s+(not\s+)?allowed|pets?\s+prohibited).{0,120}(immediate\s+eviction|evict.{0,20}immediately|eviction\s+without\s+notice)",
        "level": "high",
        "reason": "Having a pet could result in immediate eviction with no warning and no refund of deposit.",
        "tip": "The penalty is disproportionate. Ask for a warning period of at least 7 days before eviction for minor violations.",
        "confidence": 88,
        "requires_not": [],
    },
    {
        "id": "repair_request_delay",
        "pattern": r"(tenant|lessee).{0,60}(30|thirty|15|fifteen|21|twenty.?one)\s+days?.{0,60}(notice|notif).{0,60}(maintenance|repair)",
        "level": "medium",
        "reason": "You must give the landlord advance notice before they are required to fix anything — even urgent repairs.",
        "tip": "Negotiate for urgent repairs to be addressed within 48 hours without requiring advance notice.",
        "confidence": 80,
        "requires_not": [],
    },
    {
        "id": "blanket_future_amendments",
        "pattern": r"(agree[sd]?|consent[sd]?).{0,80}(all\s+future|future\s+amend|future\s+modif).{0,80}(without.{0,30}consent|as\s+deemed\s+fit|at\s+(his|her|its|the)\s+(sole\s+)?discretion)",
        "level": "high",
        "reason": "You are agreeing in advance to any future changes the landlord makes without being asked.",
        "tip": "Remove this clause. All amendments must require written consent from both parties.",
        "confidence": 91,
        "requires_not": [r"mutual\s+consent", r"written\s+agreement\s+of\s+both"],
    },
    {
        "id": "guest_restriction_every_occasion",
        "pattern": r"(no\s+guests?|guests?\s+(not\s+)?permitted).{0,100}(overnight|stay.{0,20}night).{0,100}(each\s+occasion|every\s+time|prior\s+written\s+permission)",
        "level": "medium",
        "reason": "You need written permission from the landlord every time a guest stays overnight.",
        "tip": "Negotiate for guests to be allowed for up to 7 consecutive days without requiring permission.",
        "confidence": 78,
        "requires_not": [],
    },
    {
        "id": "waiver_all_courts",
        "pattern": r"(shall\s+not|must\s+not|not\s+entitled).{0,60}(approach|file|initiate|go\s+to).{0,60}(consumer\s+court|civil\s+court|legal\s+forum|any\s+court|any\s+forum|tribunal)",
        "level": "high",
        "reason": "You are giving up your right to take any legal action or approach any court for any dispute.",
        "tip": "This clause is likely unenforceable under Indian law. Statutory rights to approach courts cannot be waived. Consult a lawyer.",
        "confidence": 94,
        "requires_not": [],
    },
    {
        "id": "all_charges_tenant_property_tax",
        "pattern": r"(tenant|lessee).{0,60}(pay|bear|responsible).{0,80}(property\s+tax|society\s+charges|any\s+(other\s+)?charges.{0,40}(authority|levied))",
        "level": "medium",
        "reason": "You are responsible for paying property tax and all government charges — these are normally the landlord's obligation.",
        "tip": "Property tax is the landlord's legal responsibility in most Indian states. Ask for this to be removed.",
        "confidence": 83,
        "requires_not": [],
    },
    {
        "id": "vacate_24_hours",
        "pattern": r"vacate.{0,60}(24\s*hours?|twenty.?four\s*hours?|one\s+day).{0,60}(notice|receiving|of\s+notice|from\s+the\s+landlord)",
        "level": "high",
        "reason": "You could be required to leave the property within just 24 hours of receiving notice.",
        "tip": "24 hours notice is likely illegal under Indian Rent Control Acts. Ask for a minimum of 30 days notice.",
        "confidence": 92,
        "requires_not": [],
    },
    {
        "id": "binding_on_heirs_no_consent",
        "pattern": r"binding.{0,60}(legal\s+heirs?|successors?|assigns?).{0,60}without.{0,40}(further\s+consent|any\s+consent|notice)",
        "level": "medium",
        "reason": "This agreement automatically applies to your family members and legal heirs without anyone's consent.",
        "tip": "Ask for a clause stating the agreement is personal and terminates when the original tenant leaves.",
        "confidence": 76,
        "requires_not": [],
    },
    # ── NEW BATCH: Employment-specific risks ──────────────────────────────────

    {
        "id": "excessive_notice_period_employee",
        "pattern": r"(employee|you).{0,60}(notice\s+period|resign).{0,60}(9[0-9]|1[0-9]{2})\s*days?",
        "level": "medium",
        "reason": "Your required resignation notice period is unusually long, which can trap you in a job you want to leave.",
        "tip": "60 days is standard for most Indian roles. Negotiate this down or ask for a buyout option.",
        "confidence": 78,
        "requires_not": [],
    },
    {
        "id": "non_compete_broad",
        "pattern": r"(shall\s+not|not\s+permitted|prohibited\s+from).{0,80}(work|employ|engage).{0,80}(competitor|similar\s+business|same\s+industry).{0,80}(any\s+(location|country|state)|worldwide|globally|india)",
        "level": "high",
        "reason": "This non-compete clause is broad enough to potentially block you from your entire industry after leaving.",
        "tip": "Indian courts generally do not enforce broad post-employment non-competes. Consult a lawyer if this is used against you.",
        "confidence": 85,
        "requires_not": [],
    },
    {
        "id": "salary_withholding_full_notice",
        "pattern": r"(salary|wages|dues|full\s+and\s+final).{0,80}(withheld|not\s+(be\s+)?released|forfeited).{0,80}(notice\s+period|resignation|clearance)",
        "level": "high",
        "reason": "Your salary can be withheld entirely if you don't serve the full notice period, even for dues you've already earned.",
        "tip": "Earned wages generally cannot be withheld under the Payment of Wages Act. Ask for partial release of dues.",
        "confidence": 87,
        "requires_not": [],
    },
    {
        "id": "forced_resignation_clause",
        "pattern": r"(deemed\s+to\s+have\s+resigned|deemed\s+resignation|automatic\s+resignation).{0,80}(absence|non[-\s]?compliance|failure\s+to)",
        "level": "high",
        "reason": "You could be treated as having resigned automatically, without any formal process or chance to explain.",
        "tip": "This bypasses your right to due process before termination. Ask for a formal show-cause step to be added.",
        "confidence": 89,
        "requires_not": [],
    },
    {
        "id": "unpaid_overtime_mandatory",
        "pattern": r"(overtime|extra\s+hours|additional\s+hours).{0,80}(no\s+(additional|extra)\s+(pay|compensation)|without\s+(additional\s+)?compensation|unpaid)",
        "level": "medium",
        "reason": "You may be required to work extra hours without additional pay.",
        "tip": "Under most state Shops and Establishments Acts, overtime must be compensated at 1.5x-2x the normal rate.",
        "confidence": 76,
        "requires_not": [],
    },
    {
        "id": "bond_penalty_resignation",
        "pattern": r"(bond|training\s+cost|penalty).{0,80}(resign|leave|quit).{0,80}(rs\.?\s*[\d,]+|lakh|lakhs)",
        "level": "high",
        "reason": "You may owe a large financial penalty if you resign before a set period, tied to training or bond costs.",
        "tip": "Employment bonds are enforceable only if the amount reflects genuine costs incurred. Ask for an itemized breakdown.",
        "confidence": 83,
        "requires_not": [],
    },
    {
        "id": "confidentiality_overreach",
        "pattern": r"confidential(ity)?.{0,100}(perpetuity|indefinitely|forever|no\s+time\s+limit)",
        "level": "medium",
        "reason": "Your confidentiality obligation has no time limit, extending indefinitely beyond your employment.",
        "tip": "Ask for a reasonable time limit (e.g. 2-5 years post-employment) on confidentiality obligations.",
        "confidence": 74,
        "requires_not": [],
    },

    # ── NEW BATCH: Rental-specific gaps ────────────────────────────────────────

    {
        "id": "key_money_non_refundable",
        "pattern": r"(key\s+money|goodwill\s+(amount|payment)|advance\s+(amount|payment)).{0,80}(non[-\s]?refundable|not\s+refundable)",
        "level": "high",
        "reason": "A one-time 'key money' or goodwill payment is being taken with no refund, separate from your security deposit.",
        "tip": "This practice is often not legally protected. Get a receipt and clarify in writing whether any part is refundable.",
        "confidence": 80,
        "requires_not": [],
    },
    {
        "id": "no_rent_receipt",
        "pattern": r"(landlord|owner).{0,60}(not\s+obligated|no\s+obligation|not\s+required).{0,60}(issue|provide|give).{0,30}receipt",
        "level": "medium",
        "reason": "The landlord isn't required to give you rent receipts, which could hurt you if you ever need proof of tenancy or for tax purposes.",
        "tip": "Ask for monthly rent receipts to be made mandatory in the agreement.",
        "confidence": 72,
        "requires_not": [],
    },
    {
        "id": "utility_disconnection_threat",
        "pattern": r"(landlord|owner).{0,60}(disconnect|cut\s+off|stop).{0,60}(electricity|water|utilit)",
        "level": "high",
        "reason": "The landlord may be permitted to cut off your electricity or water supply as a way to force compliance.",
        "tip": "Disconnecting essential utilities to force a tenant out is illegal in most Indian states, regardless of what the agreement says.",
        "confidence": 90,
        "requires_not": [],
    },
    {
        "id": "unregistered_lockin_risk",
        "pattern": r"(agreement|lease).{0,60}(not\s+(be\s+)?registered|unregistered).{0,80}(1[2-9]|2\d|3\d)\s*(month|months|year|years)",
        "level": "medium",
        "reason": "This agreement runs longer than 11 months but states it won't be registered, which can weaken your legal standing in a dispute.",
        "tip": "Agreements over 11 months should legally be registered at the Sub-Registrar's office to be fully enforceable.",
        "confidence": 79,
        "requires_not": [],
    },
    {
        "id": "broker_fee_tenant_full",
        "pattern": r"(brokerage|broker\s+fee|agent\s+fee).{0,60}(entirely|fully|100\s*%|solely).{0,40}(tenant|lessee)",
        "level": "low",
        "reason": "You are bearing the full brokerage fee, which in some markets is customarily split with the landlord.",
        "tip": "Brokerage split norms vary by city — check local convention before accepting full liability.",
        "confidence": 60,
        "requires_not": [],
    },
    {
        "id": "painting_charges_deduction",
        "pattern": r"(painting|whitewash).{0,60}(charges?|cost).{0,60}(deduct|adjust).{0,40}(deposit|advance)",
        "level": "low",
        "reason": "Painting or whitewash charges will be deducted from your deposit regardless of the property's actual condition.",
        "tip": "Ask for deductions to be based on actual documented damage, not a flat mandatory charge.",
        "confidence": 65,
        "requires_not": [],
    },
    {
        "id": "pg_no_refund_partial_month",
        "pattern": r"(paying\s+guest|pg|hostel).{0,80}(no\s+refund|non[-\s]?refundable).{0,60}(partial|part\s+of\s+the\s+month|days\s+remaining)",
        "level": "medium",
        "reason": "You won't get any refund for unused days if you leave partway through a month.",
        "tip": "Ask for pro-rated refunds for the unused portion of any paid period.",
        "confidence": 70,
        "requires_not": [],
    },

    # ── NEW BATCH: Court notice / general legal risks ──────────────────────────

    {
        "id": "admission_of_liability",
        "pattern": r"(admit|acknowledge|accept).{0,60}(liability|guilt|fault|responsibility).{0,60}(without\s+prejudice)?",
        "level": "high",
        "reason": "This document may contain language where you admit liability or fault — this can be used against you later.",
        "tip": "Do not sign any document admitting fault or liability without a lawyer reviewing it first.",
        "confidence": 82,
        "requires_not": [r"deny|dispute|without\s+admitting"],
    },
    {
        "id": "ex_parte_risk",
        "pattern": r"ex[-\s]?parte.{0,80}(order|proceed|decree)",
        "level": "high",
        "reason": "This notice mentions an ex-parte order — a ruling that can be made against you if you don't respond in time.",
        "tip": "Respond within the stated deadline. Missing it may result in a decision being made without your side being heard.",
        "confidence": 88,
        "requires_not": [],
    },
    {
        "id": "limitation_period_warning",
        "pattern": r"(limitation\s+period|within\s+(30|thirty|15|fifteen|60|sixty)\s+days\s+of\s+(receipt|service)).{0,80}(respond|reply|file|appear)",
        "level": "high",
        "reason": "There's a strict legal deadline to respond to this notice — missing it can seriously harm your case.",
        "tip": "Note the exact deadline and consult a lawyer well before it expires.",
        "confidence": 85,
        "requires_not": [],
    },
]


# ── Helper functions ──────────────────────────────────────────────────────────

def _match_rule(rule: dict, text_lower: str) -> bool:
    """Check if a rule matches, respecting requires_not exclusions."""
    if not re.search(rule["pattern"], text_lower, re.IGNORECASE | re.DOTALL):
        return False
    for excl in rule.get("requires_not", []):
        if re.search(excl, text_lower, re.IGNORECASE):
            return False
    return True


def _detect_vague_language(text: str) -> list:
    """
    Layer 3: structural vagueness detection.
    Flags clauses with dangerously open-ended language.
    """
    flags = []
    t = text.lower()

    if re.search(r"\betc\.?\b|\band\s+so\s+on\b|\binter\s+alia\b", t):
        flags.append({
            "risk_level": "medium",
            "reason": "This clause contains vague language ('etc.', 'inter alia') that could be interpreted broadly against you.",
            "tip": "Ask for all items to be listed explicitly. Vague lists are often used to include unexpected obligations.",
            "confidence": 68,
        })

    if len(text.split()) > 120 and not re.search(r"\d+\s*(day|month|year|rs\.?|rupee|percent|%)", t):
        flags.append({
            "risk_level": "medium",
            "reason": "This is a long clause with no specific numbers or timeframes — it may be intentionally vague.",
            "tip": "Ask for specific numbers, timelines, and amounts to be written in explicitly.",
            "confidence": 65,
        })

    return flags


# ── Main entry point ──────────────────────────────────────────────────────────

def flag_clause(clause_text: str) -> dict:
    """
    Flag a single clause. Returns the highest-risk match found.
    All flags are collected and sorted by confidence.
    """
    text_lower = clause_text.lower()
    all_flags = []

    # Layer 1 & 2: rule-based
    for rule in RULES:
        if _match_rule(rule, text_lower):
            all_flags.append({
                "id":         rule["id"],
                "risk_level": rule["level"],
                "reason":     rule["reason"],
                "tip":        rule["tip"],
                "confidence": rule["confidence"],
            })

    # Layer 3: structural vagueness
    all_flags.extend(_detect_vague_language(clause_text))

    if not all_flags:
        return {
            "risk_level":  "low",
            "risk_reason": None,
            "risk_tip":    None,
            "confidence":  100,
            "all_flags":   [],
        }

    # Sort: high risk first, then by confidence descending
    all_flags.sort(key=lambda f: (0 if f["risk_level"] == "high" else 1, -f["confidence"]))
    top = all_flags[0]

    return {
        "risk_level":  top["risk_level"],
        "risk_reason": top["reason"],
        "risk_tip":    top["tip"],
        "confidence":  top["confidence"],
        "all_flags":   all_flags,
    }


def flag_all_clauses(clauses: list) -> list:
    """Apply risk flagging to all clauses. Returns enriched list."""
    return [{**c, **flag_clause(c["text"])} for c in clauses]


def get_risk_summary(clauses: list) -> dict:
    """Return aggregate risk stats for a document."""
    high   = sum(1 for c in clauses if c.get("risk_level") == "high")
    medium = sum(1 for c in clauses if c.get("risk_level") == "medium")
    low    = sum(1 for c in clauses if c.get("risk_level") == "low")
    avg_confidence = (
        sum(c.get("confidence", 0) for c in clauses) / len(clauses)
        if clauses else 0
    )
    return {
        "high_risk":        high,
        "medium_risk":      medium,
        "low_risk":         low,
        "total":            len(clauses),
        "avg_confidence":   round(avg_confidence),
        "overall_risk":     "high" if high > 0 else "medium" if medium > 0 else "low",
    }
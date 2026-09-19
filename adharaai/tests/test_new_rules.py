"""
test_new_rules.py — validates the 17 rules added in the 34->51 expansion batch
(employment, rental gaps, court notice). Run standalone, same style as
test_accuracy.py.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.risk_flagger import flag_clause

CASES = [
    ("excessive_notice_period_employee", True,
     "The employee shall serve a notice period of 120 days before resignation is accepted."),
    ("excessive_notice_period_employee", False,
     "The employee shall serve a notice period of 30 days before resignation is accepted."),

    ("non_compete_broad", True,
     "The employee shall not work for a competitor anywhere in India for two years after leaving."),
    ("non_compete_broad", False,
     "The employee shall not work for a competitor within the same city for six months."),

    ("salary_withholding_full_notice", True,
     "Full and final settlement will be withheld until the notice period is completed by the employee."),
    ("salary_withholding_full_notice", False,
     "Full and final settlement will be released within 45 days of the last working day."),

    ("forced_resignation_clause", True,
     "The employee shall be deemed to have resigned in case of absence for 10 consecutive days without approval."),
    ("forced_resignation_clause", False,
     "The employee may resign by submitting a written notice for personal reasons."),

    ("unpaid_overtime_mandatory", True,
     "Employees may be required to work overtime without additional compensation."),
    ("unpaid_overtime_mandatory", False,
     "Employees may be required to work overtime, which will be compensated at 1.5x the standard rate."),

    ("bond_penalty_resignation", True,
     "The employee's training bond requires that if they resign before 2 years, a penalty of Rs. 2,00,000 shall apply."),
    ("bond_penalty_resignation", False,
     "The employee may resign at any time by providing 60 days written notice."),

    ("confidentiality_overreach", True,
     "The employee agrees to maintain confidentiality of company information in perpetuity, even after termination."),
    ("confidentiality_overreach", False,
     "The employee agrees to maintain confidentiality of company information for a period of 3 years after termination."),

    ("key_money_non_refundable", True,
     "A goodwill amount of Rs. 50,000 shall be paid by the tenant, which is non-refundable."),
    ("key_money_non_refundable", False,
     "A goodwill amount of Rs. 50,000 shall be paid by the tenant, refundable upon vacating the premises."),

    ("no_rent_receipt", True,
     "The landlord is not obligated to issue a rent receipt to the tenant."),
    ("no_rent_receipt", False,
     "The landlord shall issue a rent receipt to the tenant every month."),

    ("utility_disconnection_threat", True,
     "The landlord may disconnect the electricity supply if rent is not paid on time."),
    ("utility_disconnection_threat", False,
     "The landlord shall ensure uninterrupted electricity and water supply throughout the tenancy."),

    ("unregistered_lockin_risk", True,
     "This lease agreement shall not be registered with the Sub-Registrar despite being for a period of 24 months."),
    ("unregistered_lockin_risk", False,
     "This lease agreement, for a period of 24 months, shall be duly registered with the Sub-Registrar."),

    ("broker_fee_tenant_full", True,
     "The brokerage fee shall be borne entirely by the tenant."),
    ("broker_fee_tenant_full", False,
     "The brokerage fee shall be shared equally between the landlord and tenant."),

    ("painting_charges_deduction", True,
     "Painting charges will be deducted from the security deposit at the time of vacating, irrespective of condition."),
    ("painting_charges_deduction", False,
     "Painting charges, if any, will be based on actual damage assessed at the time of vacating."),

    ("pg_no_refund_partial_month", True,
     "This PG accommodation offers no refund for the partial month if the resident vacates early."),
    ("pg_no_refund_partial_month", False,
     "This PG accommodation offers a pro-rated refund for any unused days if the resident vacates early."),

    ("admission_of_liability", True,
     "The respondent hereby acknowledges responsibility for the damage caused to the property."),
    ("admission_of_liability", False,
     "The respondent, without admitting liability, agrees to pay a goodwill sum to resolve the matter."),

    ("ex_parte_risk", True,
     "The court may pass an ex-parte order if you fail to appear on the given date."),
    ("ex_parte_risk", False,
     "The court will schedule a hearing where both parties will be given an opportunity to be heard."),

    ("limitation_period_warning", True,
     "Within 30 days of receipt of this notice, you must respond in writing, failing which further action will be taken."),
    ("limitation_period_warning", False,
     "You may contact our office at any time for clarification regarding this notice."),
]


def main():
    print("=" * 70)
    print("NEW RULES VALIDATION TEST (34 -> 51 batch)")
    print("=" * 70)

    passed = 0
    failed = 0
    false_positives = 0
    missed = 0

    for rule_id, expect_match, text in CASES:
        result = flag_clause(text)
        matched_ids = [f["id"] for f in result.get("all_flags", [])]
        got_match = rule_id in matched_ids

        ok = got_match == expect_match
        label = "positive" if expect_match else "negative"
        status = "PASS" if ok else "FAIL"

        if ok:
            passed += 1
        else:
            failed += 1
            if expect_match and not got_match:
                missed += 1
            if not expect_match and got_match:
                false_positives += 1

        print(f"[{status}] {rule_id} ({label})")
        if not ok:
            print(f"    -> expected match={expect_match}, got={got_match}, all flags matched: {matched_ids}")

    total = len(CASES)
    print()
    print("-" * 70)
    print(f"Total test cases : {total}")
    print(f"Passed           : {passed}")
    print(f"Failed           : {failed}")
    print(f"  False positives (matched when it shouldn't) : {false_positives}")
    print(f"  Missed matches  (didn't match when it should): {missed}")
    print(f"Pass rate        : {round(100 * passed / total, 1)}%")
    print("-" * 70)


if __name__ == "__main__":
    main()

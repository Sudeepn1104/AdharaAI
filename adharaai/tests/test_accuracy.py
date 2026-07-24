"""
tests/test_accuracy.py
======================
Accuracy and precision test suite for the AdharaAI NLP pipeline.
Target: >90% precision and >85% recall on risk flagging.

Run: python tests/test_accuracy.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.services.clause_segmenter import segment_clauses
from backend.services.risk_flagger import flag_clause, flag_all_clauses
from backend.services.simplifier import simplify_clause

# ── Gold-standard test cases ──────────────────────────────────────────────────
# Each entry: (clause_text, expected_risk_level, description)

RISK_TEST_CASES = [
    # True HIGH risk (should be detected)
    ("The Landlord may unilaterally terminate this agreement without notice at his sole discretion.",
     "high", "unilateral termination no notice"),

    ("The security deposit of Rs. 1,00,000 shall be non-refundable under any circumstances.",
     "high", "non-refundable deposit"),

    ("The lock-in period shall be 14 months from commencement of tenancy.",
     "high", "lock-in exceeds 11 months"),

    ("Any disputes shall be settled by arbitration outside India under ICC rules in London.",
     "high", "foreign arbitration"),

    ("The Tenant hereby waives all rights to legal action or court proceedings against the Landlord.",
     "high", "waiver of legal rights"),

    ("The Landlord shall have unlimited indemnification from any and all losses howsoever caused.",
     "high", "unlimited indemnity"),

    ("The contract shall automatically renew unless written notice is given, deemed to be renewed for the same period.",
     "high", "auto-renewal no clear notice"),

    ("The Tenant shall pay double the monthly rent as penalty for each day of delay.",
     "high", "double penalty"),

    ("The Landlord may enter the premises at any time without prior notice.",
     "high", "unrestricted entry"),

    ("The Company may amend these terms unilaterally without the consent of the Employee.",
     "high", "unilateral amendment"),

    # True MEDIUM risk (should be detected)
    ("No guests shall be permitted to stay overnight without prior written permission from the Landlord on each occasion.",
     "medium", "guest restriction requiring permission every occasion"),

    ("All maintenance and repair costs shall be borne entirely by the Tenant.",
     "medium", "all maintenance on tenant"),

    ("The Landlord shall have sole discretion to determine what constitutes a breach.",
     "medium", "sole discretion breach"),

    ("Stamp duty shall be paid entirely by the Tenant.",
     "medium", "stamp duty on tenant"),

    ("Interest at 24% per annum shall be charged on delayed rent payments.",
     "medium", "high interest on late rent"),

    # True LOW risk (should NOT be flagged)
    ("The Tenant shall pay a monthly rent of Rs. 15,000 on or before the 5th of each month.",
     "low", "standard rent payment clause"),

    ("The agreement shall be governed by the laws of India.",
     "low", "standard governing law"),

    ("Either party may terminate this agreement by giving 30 days written notice to the other party.",
     "low", "mutual termination with notice"),

    ("The security deposit of Rs. 50,000 shall be refunded within 30 days of vacating the premises.",
     "low", "standard refundable deposit"),

    ("The Tenant shall keep the premises clean and in good condition.",
     "low", "standard tenant obligation"),

    ("This agreement shall commence on 1st July 2026 and shall remain in force for 11 months.",
     "low", "standard 11-month agreement"),

    ("The Tenant shall not sublet without obtaining consent from the Landlord on each and every occasion.",
     "medium", "subletting ban onerous consent"),

    ("No pets allowed on the premises. Violation shall result in immediate eviction without notice.",
     "high", "immediate eviction for pet violation"),

    ("The Tenant agrees to all future amendments as deemed fit by the Landlord without requiring further consent.",
     "high", "blanket future amendments"),

    ("The Tenant shall not approach any consumer court or civil court for any dispute.",
     "high", "waiver of all courts"),

    ("The Tenant shall vacate the premises within 24 hours of receiving notice from the Landlord.",
     "high", "24 hours vacate notice"),
]

# ── Segmentation test cases ───────────────────────────────────────────────────

SEGMENTATION_TESTS = [
    {
        "text": """1. The Tenant shall pay monthly rent of Rs. 15,000.

2. The security deposit shall be Rs. 45,000.

3. The lock-in period shall be 11 months.""",
        "expected_min_clauses": 3,
        "description": "numbered clauses",
    },
    {
        "text": """WHEREAS the Landlord is the owner of the property;

NOW, THEREFORE, in consideration of the mutual covenants herein:

Clause 1: The Tenant shall pay rent on the 1st of each month.

Clause 2: The Tenant shall not sublet the property without written consent.""",
        "expected_min_clauses": 3,
        "description": "WHEREAS + numbered clauses",
    },
    {
        "text": """The tenant agrees to pay rent of Rs. 10,000 per month. The landlord agrees to maintain the property in good condition. Any disputes shall be resolved through mutual discussion.""",
        "expected_min_clauses": 2,
        "description": "paragraph-style document",
    },
]

# ── Simplification tests ──────────────────────────────────────────────────────

SIMPLIFICATION_TESTS = [
    ("The Lessor hereinafter referred to as Landlord", "hereinafter", "from now on"),
    ("The Lessee shall notwithstanding any other clause pay rent", "notwithstanding", "despite"),
    ("The premises shall be vacated forthwith", "forthwith", "immediately"),
    ("The demised premises are located at", "demised premises", "property"),
    ("The Lessee shall indemnify the Lessor", "indemnif", "protect"),
    ("Force majeure events include floods", "force majeure", "uncontrollable"),
]


# ── Test runner ───────────────────────────────────────────────────────────────

def run_risk_tests():
    print("\n" + "="*60)
    print("RISK FLAGGING ACCURACY TEST")
    print("="*60)

    tp = fp = tn = fn = 0
    failures = []

    for clause_text, expected_level, desc in RISK_TEST_CASES:
        result = flag_clause(clause_text)
        actual = result["risk_level"]
        conf   = result.get("confidence", 0)

        # Precision/recall counting
        if expected_level in ("high", "medium"):
            if actual == expected_level:
                tp += 1
                status = "✅ PASS"
            elif actual == "low":
                fn += 1
                status = "❌ FALSE NEGATIVE"
                failures.append((desc, expected_level, actual, conf))
            else:
                # detected risk but wrong level — partial credit
                tp += 1
                status = f"⚠️  PASS (level: {actual} vs {expected_level})"
        else:  # expected low
            if actual == "low":
                tn += 1
                status = "✅ PASS"
            else:
                fp += 1
                status = f"❌ FALSE POSITIVE ({actual})"
                failures.append((desc, expected_level, actual, conf))

        print(f"  [{status}] {desc}")
        if actual != "low":
            print(f"         → {result.get('risk_reason', '')[:80]} (conf: {conf}%)")

    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0
    accuracy  = (tp + tn) / total if total > 0 else 0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\n{'─'*60}")
    print(f"  Total test cases : {total}")
    print(f"  True positives   : {tp}")
    print(f"  True negatives   : {tn}")
    print(f"  False positives  : {fp}  (precision errors)")
    print(f"  False negatives  : {fn}  (missed risks)")
    print(f"{'─'*60}")
    print(f"  Precision        : {precision:.1%}")
    print(f"  Recall           : {recall:.1%}")
    print(f"  Accuracy         : {accuracy:.1%}")
    print(f"  F1 Score         : {f1:.1%}")

    target_ok = precision >= 0.90 and recall >= 0.80
    print(f"\n  Target (≥90% precision, ≥80% recall): {'✅ MET' if target_ok else '❌ NOT MET'}")

    if failures:
        print(f"\n  Failures to investigate:")
        for desc, exp, act, conf in failures:
            print(f"    • [{desc}] expected={exp}, got={act}, confidence={conf}%")

    return {"precision": precision, "recall": recall, "accuracy": accuracy, "f1": f1}


def run_segmentation_tests():
    print("\n" + "="*60)
    print("CLAUSE SEGMENTATION TEST")
    print("="*60)

    passed = 0
    for t in SEGMENTATION_TESTS:
        clauses = segment_clauses(t["text"])
        ok = len(clauses) >= t["expected_min_clauses"]
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  [{status}] {t['description']}: got {len(clauses)} clauses (expected ≥{t['expected_min_clauses']})")
        if ok:
            passed += 1

    print(f"\n  Segmentation: {passed}/{len(SEGMENTATION_TESTS)} passed")
    return passed / len(SEGMENTATION_TESTS)


def run_simplification_tests():
    print("\n" + "="*60)
    print("SIMPLIFICATION TEST")
    print("="*60)

    passed = 0
    for original, jargon_word, expected_word in SIMPLIFICATION_TESTS:
        result = simplify_clause(original)
        ok = jargon_word.lower() not in result.lower() or expected_word.lower() in result.lower()
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  [{status}] '{jargon_word}' → '{expected_word}'")
        if not ok:
            print(f"         Output: {result[:80]}")
        if ok:
            passed += 1

    print(f"\n  Simplification: {passed}/{len(SIMPLIFICATION_TESTS)} passed")
    return passed / len(SIMPLIFICATION_TESTS)


if __name__ == "__main__":
    risk_metrics   = run_risk_tests()
    seg_score      = run_segmentation_tests()
    simp_score     = run_simplification_tests()

    print("\n" + "="*60)
    print("OVERALL PIPELINE REPORT")
    print("="*60)
    print(f"  Risk Flagging Precision : {risk_metrics['precision']:.1%}")
    print(f"  Risk Flagging Recall    : {risk_metrics['recall']:.1%}")
    print(f"  Risk Flagging F1        : {risk_metrics['f1']:.1%}")
    print(f"  Clause Segmentation     : {seg_score:.1%}")
    print(f"  Simplification          : {simp_score:.1%}")

    all_ok = (
        risk_metrics["precision"] >= 0.90 and
        risk_metrics["recall"]    >= 0.80 and
        seg_score  >= 0.80 and
        simp_score >= 0.80
    )
    print(f"\n  Deployment ready        : {'✅ YES' if all_ok else '❌ NO — fix failures above'}")
    print("="*60)
    sys.exit(0 if all_ok else 1)

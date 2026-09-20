"""
test_classifier.py — validates the hybrid classifier's fail-closed behavior:
missing weights, key mismatch, and fallback to rules. Run standalone, same
style as test_accuracy.py.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import shutil
import backend.services.classifier as classifier


def reset_classifier_state():
    """Force a fresh _load_model() call on the next classify_clause()."""
    classifier._tokenizer = None
    classifier._model = None
    classifier._risk_encoder = None
    classifier._type_encoder = None
    classifier._model_loaded = False


def test_missing_weights_falls_back():
    reset_classifier_state()
    real_path = classifier.MODEL_PATH
    fake_path = real_path + "_missing_test"
    if os.path.exists(fake_path):
        shutil.rmtree(fake_path)
    os.makedirs(fake_path)
    # Copy everything except model.safetensors, so the folder exists but
    # weights are absent — this is the exact case Savin flagged.
    for name in os.listdir(real_path):
        if name != "model.safetensors":
            src = os.path.join(real_path, name)
            dst = os.path.join(fake_path, name)
            if os.path.isfile(src):
                shutil.copy(src, dst)

    classifier.MODEL_PATH = fake_path
    result = classifier.classify_clause("Tenant shall pay rent on the 5th of each month.")
    still_unavailable = classifier.is_available() is False
    classifier.MODEL_PATH = real_path
    shutil.rmtree(fake_path)

    passed = result["source"] == "fallback" and still_unavailable
    print(f"{'PASS' if passed else 'FAIL'}: missing weights falls back to rules  -> {result}")
    return passed


def test_real_weights_load():
    reset_classifier_state()
    ok = classifier.is_available()
    print(f"{'PASS' if ok else 'FAIL'}: real weights load successfully -> is_available()={ok}")
    return ok


def test_classify_returns_expected_shape():
    reset_classifier_state()
    result = classifier.classify_clause("The security deposit is refundable within 30 days.")
    keys_ok = all(k in result for k in
                  ["risk_level", "clause_type", "risk_confidence", "type_confidence", "source"])
    print(f"{'PASS' if keys_ok else 'FAIL'}: classify_clause returns expected keys -> {result}")
    return keys_ok


if __name__ == "__main__":
    results = [
        test_missing_weights_falls_back(),
        test_real_weights_load(),
        test_classify_returns_expected_shape(),
    ]
    passed = sum(results)
    print(f"\n{passed}/{len(results)} tests passed")
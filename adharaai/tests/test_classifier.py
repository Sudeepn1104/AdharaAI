"""
test_classifier.py - validates the hybrid classifier's fail-closed behavior:
missing weights, key mismatch, and fallback to rules. Pytest-compatible.

Tests needing the real InLegalBERT model files (gitignored, absent in a
clean clone) are skipped automatically when those files aren't present.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import shutil
import pytest
import backend.services.classifier as classifier


def reset_classifier_state():
    classifier._tokenizer = None
    classifier._model = None
    classifier._risk_encoder = None
    classifier._type_encoder = None
    classifier._model_loaded = False


MODEL_FILES_PRESENT = os.path.exists(classifier.MODEL_PATH) and os.path.exists(
    os.path.join(classifier.MODEL_PATH, "model.safetensors")
)


def test_nonexistent_model_path_falls_back():
    """No model files at all (e.g. a clean clone) -> must fall back to
    rules, never crash. Needs no files, always runs."""
    reset_classifier_state()
    real_path = classifier.MODEL_PATH
    classifier.MODEL_PATH = real_path + "_does_not_exist"

    result = classifier.classify_clause("Tenant shall pay rent on the 5th of each month.")
    available = classifier.is_available()

    classifier.MODEL_PATH = real_path

    assert result["source"] == "fallback"
    assert available is False


@pytest.mark.skipif(not MODEL_FILES_PRESENT, reason="requires real InLegalBERT weights, not present in this clone")
def test_missing_safetensors_falls_back():
    """Model folder + config/tokenizer exist, but model.safetensors is
    missing -> must fall back to rules, not serve random-head predictions."""
    reset_classifier_state()
    real_path = classifier.MODEL_PATH
    fake_path = real_path + "_missing_weights_test"
    if os.path.exists(fake_path):
        shutil.rmtree(fake_path)
    os.makedirs(fake_path)
    for name in os.listdir(real_path):
        if name != "model.safetensors":
            src = os.path.join(real_path, name)
            if os.path.isfile(src):
                shutil.copy(src, os.path.join(fake_path, name))

    classifier.MODEL_PATH = fake_path
    result = classifier.classify_clause("Tenant shall pay rent on the 5th of each month.")
    available = classifier.is_available()
    classifier.MODEL_PATH = real_path
    shutil.rmtree(fake_path)

    assert result["source"] == "fallback"
    assert available is False


@pytest.mark.skipif(not MODEL_FILES_PRESENT, reason="requires real InLegalBERT weights, not present in this clone")
def test_real_weights_load():
    reset_classifier_state()
    assert classifier.is_available() is True


@pytest.mark.skipif(not MODEL_FILES_PRESENT, reason="requires real InLegalBERT weights, not present in this clone")
def test_classify_returns_expected_shape():
    reset_classifier_state()
    result = classifier.classify_clause("The security deposit is refundable within 30 days.")
    for key in ["risk_level", "clause_type", "risk_confidence", "type_confidence", "source"]:
        assert key in result
    assert result["source"] == "bert"
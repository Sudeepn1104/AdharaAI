"""
test_classifier_onnx.py - checks the production ONNX path of classifier.py
using a tiny generated model (no real InLegalBERT weights needed).
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

onnx = pytest.importorskip("onnx")
pytest.importorskip("onnxruntime")
tokenizers = pytest.importorskip("tokenizers")

from onnx import TensorProto, helper

import backend.services.classifier as classifier

RISK = ["high", "low", "medium"]
TYPES = ["deposit", "payment", "termination"]


def _tiny_model(path):
    """ONNX graph: logits = mean(one_hot-ish(input_ids)) @ W  for both heads."""
    vocab = 8
    w_risk = np.zeros((vocab, 3), dtype=np.float32)
    w_risk[3, 0] = 5.0  # token id 3 ("deposit") -> "high"
    w_type = np.zeros((vocab, 3), dtype=np.float32)
    w_type[3, 0] = 5.0  # token id 3 -> "deposit"
    nodes = [
        helper.make_node("Cast", ["input_ids"], ["ids32"], to=TensorProto.INT32),
        helper.make_node("Gather", ["emb", "ids32"], ["e"]),            # [b, s, vocab]
        helper.make_node("ReduceMax", ["e"], ["pooled"], axes=[1], keepdims=0),
        helper.make_node("MatMul", ["pooled", "w_risk"], ["risk_logits"]),
        helper.make_node("MatMul", ["pooled", "w_type"], ["type_logits"]),
        helper.make_node("Identity", ["attention_mask"], ["unused_mask"]),
    ]
    graph = helper.make_graph(
        nodes, "tiny",
        [helper.make_tensor_value_info("input_ids", TensorProto.INT64, ["b", "s"]),
         helper.make_tensor_value_info("attention_mask", TensorProto.INT64, ["b", "s"])],
        [helper.make_tensor_value_info("risk_logits", TensorProto.FLOAT, ["b", 3]),
         helper.make_tensor_value_info("type_logits", TensorProto.FLOAT, ["b", 3]),
         helper.make_tensor_value_info("unused_mask", TensorProto.INT64, ["b", "s"])],
        initializer=[
            helper.make_tensor("emb", TensorProto.FLOAT, [vocab, vocab], np.eye(vocab, dtype=np.float32).flatten()),
            helper.make_tensor("w_risk", TensorProto.FLOAT, [vocab, 3], w_risk.flatten()),
            helper.make_tensor("w_type", TensorProto.FLOAT, [vocab, 3], w_type.flatten()),
        ],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.save(model, path)


def _tiny_tokenizer(path):
    from tokenizers import Tokenizer, models, pre_tokenizers
    vocab = {"[UNK]": 0, "[CLS]": 1, "[SEP]": 2, "deposit": 3, "rent": 4, "pay": 5, "the": 6, "tenant": 7}
    tok = Tokenizer(models.WordLevel(vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    tok.save(path)


@pytest.fixture
def onnx_dir(tmp_path):
    _tiny_model(str(tmp_path / "model.onnx"))
    _tiny_tokenizer(str(tmp_path / "tokenizer.json"))
    (tmp_path / "labels.json").write_text(json.dumps({"risk": RISK, "type": TYPES}))
    real = classifier.ONNX_PATH
    classifier.ONNX_PATH = str(tmp_path)
    for name in ["_onnx_session", "_onnx_tokenizer", "_labels", "_backend", "_model"]:
        setattr(classifier, name, None)
    classifier._model_loaded = False
    yield tmp_path
    classifier.ONNX_PATH = real
    classifier._model_loaded = False
    classifier._backend = None
    classifier._onnx_session = None


def test_onnx_path_loads_and_predicts(onnx_dir):
    assert classifier.is_available() is True
    assert classifier.backend_name() == "onnx"
    result = classifier.classify_clause("the tenant deposit")
    assert result["source"] == "bert"
    assert result["risk_level"] == "high"
    assert result["clause_type"] == "deposit"
    assert 0 <= result["risk_confidence"] <= 100


def test_onnx_missing_labels_falls_back(onnx_dir):
    os.remove(onnx_dir / "labels.json")
    real_torch = classifier.MODEL_PATH
    classifier.MODEL_PATH = real_torch + "_does_not_exist"
    try:
        assert classifier.classify_clause("the tenant deposit")["source"] == "fallback"
    finally:
        classifier.MODEL_PATH = real_torch

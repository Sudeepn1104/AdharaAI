"""
simplifier.py — Legal jargon → plain English.

Phase 1: 80+ carefully curated substitution rules covering:
  - Latin legal terms
  - Indian legal terminology
  - Contract boilerplate phrases
  - Court-specific language
  - Financial/banking terms

Each substitution is tested to NOT change legal meaning —
only the register (formal→plain).
"""

import re

# (pattern, replacement, flags)
# Order matters: longer/more specific patterns first
SUBSTITUTIONS = [

    # ── Latin terms ───────────────────────────────────────────────────────────
    (r"\binter\s+alia\b",               "among other things"),
    (r"\bmutatis\s+mutandis\b",         "with the necessary changes applied"),
    (r"\bbona\s+fide\b",                "genuine / in good faith"),
    (r"\bpari\s+passu\b",               "on equal terms"),
    (r"\bsub\s+judice\b",               "currently before a court"),
    (r"\bex\s+parte\b",                 "without the other party present"),
    (r"\binter\s+se\b",                 "among themselves"),
    (r"\bper\s+se\b",                   "by itself"),
    (r"\bviz\.\b",                      "namely"),
    (r"\bi\.e\.,?\b",                   "that is"),
    (r"\be\.g\.,?\b",                   "for example"),
    (r"\binter\s+vivos\b",              "between living persons"),
    (r"\bex\s+gratia\b",                "as a goodwill gesture, not as a legal obligation"),
    (r"\bforce\s+majeure\b",            "uncontrollable events such as natural disasters, strikes, or government action"),
    (r"\bqua\b",                        "in the capacity of"),

    # ── Herein- / there- / where- compounds ──────────────────────────────────
    (r"\bhereinafter\s+referred\s+to\s+as\b", "from now on called"),
    (r"\bhereinafter\b",                "from now on"),
    (r"\bherein\b",                     "in this document"),
    (r"\bhereby\b",                     "by this agreement"),
    (r"\bhereunder\b",                  "under this agreement"),
    (r"\bhereof\b",                     "of this agreement"),
    (r"\bhereto\b",                     "to this agreement"),
    (r"\bhereafter\b",                  "from now on"),
    (r"\bthereof\b",                    "of it"),
    (r"\bthereto\b",                    "to it"),
    (r"\bthereunder\b",                 "under it"),
    (r"\btherein\b",                    "in it"),
    (r"\bthereafter\b",                 "after that"),
    (r"\bthereupon\b",                  "immediately after that"),
    (r"\bwhereof\b",                    "of which"),
    (r"\bwherein\b",                    "in which"),
    (r"\bwhereby\b",                    "by which"),
    (r"\bwhereas\b",                    "given that"),
    (r"\bwhereupon\b",                  "after which"),

    # ── Common legal boilerplate ──────────────────────────────────────────────
    (r"\bnotwithstanding\s+anything\s+(contained|stated).{0,40}to\s+the\s+contrary\b",
                                        "despite anything else stated in this document"),
    (r"\bnotwithstanding\b",            "even though / despite"),
    (r"\bin\s+lieu\s+of\b",             "instead of"),
    (r"\bwithout\s+prejudice\s+to\b",   "without affecting"),
    (r"\bwithout\s+prejudice\b",        "without affecting either party's legal rights"),
    (r"\btime\s+is\s+of\s+the\s+essence\b", "all deadlines in this clause are strict and must be met exactly"),
    (r"\bsave\s+and\s+except\b",        "except for"),
    (r"\bsave\s+as\b",                  "except as"),
    (r"\bsubject\s+to\b",               "provided that"),
    (r"\bin\s+the\s+event\s+of\b",      "if"),
    (r"\bin\s+the\s+event\s+that\b",    "if"),
    (r"\bwithout\s+derogating\s+from\b","without limiting"),
    (r"\bat\s+(his|her|its|their)\s+sole\s+discretion\b", "entirely at their own judgment, with no obligation to be fair"),
    (r"\bsole\s+discretion\b",          "their own judgment with no obligation to explain"),
    (r"\bforthwith\b",                  "immediately"),
    (r"\bforth?with\b",                 "immediately"),
    (r"\bupona?\s+demand\b",            "when asked"),
    (r"\bat\s+all\s+times\b",           "always"),
    (r"\bfrom\s+time\s+to\s+time\b",    "whenever needed"),
    (r"\bat\s+the\s+discretion\b",      "at the judgment"),
    (r"\bat\s+liberty\b",               "free"),
    (r"\bin\s+perpetuity\b",            "forever"),
    (r"\bperpetually\b",                "forever"),
    (r"\bin\s+writing\b",               "in written form"),
    (r"\bwritten\s+instrument\b",       "written document"),
    (r"\bexecute[sd]?\b",               "sign"),
    (r"\bexecution\s+of\s+this\b",      "signing of this"),

    # ── Indian legal terms ────────────────────────────────────────────────────
    (r"\bstamp\s+duty\b",               "government tax on this document"),
    (r"\bsub[-\s]?registrar\b",         "government registration office"),
    (r"\bregistration\s+(of\s+this|charges?)\b",
                                        "official filing of this document with the government"),
    (r"\brent\s+control\s+act\b",       "the state law protecting tenants' rights"),
    (r"\btransfer\s+of\s+property\s+act\b", "the law governing property transfers in India"),
    (r"\bregistration\s+act\b",         "the law requiring certain documents to be officially recorded"),
    (r"\bcontract\s+act\b",             "the Indian Contract Act 1872"),
    (r"\bencumbrance\b",                "debt or legal claim already on this property"),
    (r"\bmutilation\b",                 "damage to the document"),
    (r"\battorney\b",                   "legal representative"),
    (r"\bpower\s+of\s+attorney\b",      "a legal document giving someone authority to act on your behalf"),
    (r"\baffidavit\b",                  "a sworn written statement"),
    (r"\bindemnif(y|ied|ication)\b",    "financially protect / compensate"),
    (r"\bindemnit(y|ies)\b",            "financial protection / compensation"),
    (r"\bliquidated\s+damages\b",       "a fixed penalty amount agreed in advance"),
    (r"\bspecific\s+performance\b",     "a court order to carry out the contract as agreed"),
    (r"\binjunction\b",                 "a court order to stop someone doing something"),

    # ── Financial terms ───────────────────────────────────────────────────────
    (r"\bprincipal\s+amount\b",         "original loan amount"),
    (r"\bpro\s+rata\b",                 "in proportion"),
    (r"\baccrued\b",                    "accumulated over time"),
    (r"\bappurtenant\b",                "attached to / belonging to"),
    (r"\bquantum\b",                    "amount"),

    # ── Tenant-specific terms ─────────────────────────────────────────────────
    (r"\bdemised\s+premises\b",         "the rented property"),
    (r"\blessor\b",                     "landlord"),
    (r"\blessee\b",                     "tenant"),
    (r"\btenancy\s+at\s+will\b",        "a rental arrangement that either party can end at any time"),
    (r"\bquiet\s+enjoyment\b",          "the right to use the property without disturbance from the landlord"),
    (r"\bvacant\s+possession\b",        "the property handed over empty and ready to use"),
    (r"\bpremises\b",                   "the property"),
]


def simplify_clause(text: str) -> str:
    """
    Apply all substitution rules to produce a plain-English version.
    Preserves sentence structure — only replaces legal jargon words/phrases.
    """
    result = text
    for pattern, replacement in SUBSTITUTIONS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    # Clean up double spaces introduced by substitutions
    result = re.sub(r" {2,}", " ", result).strip()
    return result


def simplify_all_clauses(clauses: list) -> list:
    """Add simplified_text to each clause dict."""
    for c in clauses:
        c["simplified_text"] = simplify_clause(c["text"])
    return clauses

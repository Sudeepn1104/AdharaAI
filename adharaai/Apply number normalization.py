"""
apply_number_normalization.py

Run this once from your project root:
    python apply_number_normalization.py

It patches backend/services/risk_flagger.py to add spelled-out number
normalization ("ninety days" -> "90 days") for rule matching, without
touching the original clause text shown to users.

Safe to run multiple times -- it checks whether the patch is already
applied before making changes.
"""
import re

PATH = "backend/services/risk_flagger.py"

NORMALIZATION_BLOCK = '''

# ── Number-word normalization ──────────────────────────────────────────────
# Converts spelled-out numbers ("ninety days", "twenty-four hours") to
# digits, purely for rule-matching purposes. Many rules below use \\d+
# patterns and would silently miss word-form numbers without this.
# NEVER apply this to text shown to the user -- only to the text_lower
# copy used for regex matching.

_NUMBER_WORDS = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
    'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19,
    'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
    'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
}
_SCALE_WORDS = {'hundred': 100}
_ALL_NUM_WORDS = set(_NUMBER_WORDS) | set(_SCALE_WORDS) | {'and'}
_NUM_WORD_ALT = "|".join(sorted(_ALL_NUM_WORDS, key=len, reverse=True))
_NUMBER_SPAN_RE = re.compile(
    rf"\\b(?:{_NUM_WORD_ALT})(?:[\\s-]+(?:{_NUM_WORD_ALT}))*\\b",
    re.IGNORECASE,
)


def _words_to_int(span: str) -> int:
    tokens = re.split(r"[\\s-]+", span.lower())
    total, current = 0, 0
    for tok in tokens:
        if tok == "and":
            continue
        elif tok in _SCALE_WORDS:
            current = (current or 1) * _SCALE_WORDS[tok]
        elif tok in _NUMBER_WORDS:
            current += _NUMBER_WORDS[tok]
    total += current
    return total


def normalize_numbers(text: str) -> str:
    """Convert spelled-out numbers to digits, for rule-matching only."""
    def _replace(m):
        span = m.group(0)
        value = _words_to_int(span)
        if value == 0 and span.lower().strip() != "zero":
            return span
        return str(value)

    return _NUMBER_SPAN_RE.sub(_replace, text)
'''

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

if "_NUMBER_SPAN_RE" in content:
    print("Already patched -- normalization block found. No changes made.")
else:
    # Insert the normalization block right after the initial imports
    marker = "import re\nfrom typing import Optional"
    if marker not in content:
        raise SystemExit(
            "Could not find the expected import lines at the top of the file. "
            "Open risk_flagger.py and check the first two lines match:\n"
            "  import re\n  from typing import Optional"
        )
    content = content.replace(marker, marker + NORMALIZATION_BLOCK, 1)

    # Update flag_clause() to normalize numbers before matching
    old_line = 'text_lower = clause_text.lower()'
    new_line = 'text_lower = normalize_numbers(clause_text.lower())'
    if old_line not in content:
        raise SystemExit(
            "Could not find 'text_lower = clause_text.lower()' inside flag_clause(). "
            "The normalization functions were added, but you'll need to manually "
            "change that line to: text_lower = normalize_numbers(clause_text.lower())"
        )
    content = content.replace(old_line, new_line, 1)

    with open(PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print("Patched successfully:")
    print("  1. Added normalize_numbers() near the top of the file")
    print("  2. Updated flag_clause() to use it when matching rules")
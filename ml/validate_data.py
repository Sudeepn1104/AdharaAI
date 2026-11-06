"""
validate_data.py - data quality gate for AdharaAI training CSVs (runs in CI).

Checks:
  * exactly the 7 schema columns, in order
  * no empty clause_text / risk_level / clause_type / simplified_text
  * no duplicate clause_text
  * risk_level only low / medium / high
  * every clause_type has at least MIN_PER_TYPE rows (enough to train on)

Usage:
    python ml/validate_data.py adharaai/Data/adharaai_deployment_ready_v3.csv

Exit code 1 on any failure, so CI blocks a bad dataset from being merged.
"""

import sys

import pandas as pd

SCHEMA = ["clause_text", "risk_level", "clause_type", "risk_reason",
          "simplified_text", "tip", "source_file"]
REQUIRED_NON_EMPTY = ["clause_text", "risk_level", "clause_type", "simplified_text"]
RISK_LEVELS = {"low", "medium", "high"}
MIN_PER_TYPE = 10


def validate(path: str) -> list:
    errors = []
    df = pd.read_csv(path)

    if list(df.columns) != SCHEMA:
        return [f"columns are {list(df.columns)}, expected {SCHEMA}"]

    for col in REQUIRED_NON_EMPTY:
        empty = df[col].isna() | (df[col].astype(str).str.strip() == "")
        if empty.any():
            errors.append(f"{col}: {int(empty.sum())} empty value(s) at rows {list(df.index[empty][:5])}")

    dupes = df["clause_text"].astype(str).str.strip().str.lower().duplicated()
    if dupes.any():
        errors.append(f"{int(dupes.sum())} duplicate clause_text row(s) at rows {list(df.index[dupes][:5])}")

    bad_risk = ~df["risk_level"].isin(RISK_LEVELS)
    if bad_risk.any():
        errors.append(f"unknown risk_level values: {sorted(df.loc[bad_risk, 'risk_level'].astype(str).unique())}")

    counts = df["clause_type"].value_counts()
    small = counts[counts < MIN_PER_TYPE]
    if not small.empty:
        errors.append(f"clause types with fewer than {MIN_PER_TYPE} rows: {small.to_dict()}")

    print(f"{path}: {len(df)} rows, {df['clause_type'].nunique()} clause types")
    print("  risk mix:", df["risk_level"].value_counts().to_dict())
    return errors


def main():
    paths = sys.argv[1:]
    if not paths:
        sys.exit("usage: validate_data.py <csv> [<csv> ...]")
    failed = False
    for p in paths:
        errs = validate(p)
        for e in errs:
            print(f"  FAIL: {e}")
        failed = failed or bool(errs)
    if failed:
        sys.exit(1)
    print("Data checks passed.")


if __name__ == "__main__":
    main()

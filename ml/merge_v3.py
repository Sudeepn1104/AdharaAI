import pandas as pd

D = r"C:\Users\Sudeep Nayak\Downloads"
P = D + r"\AdharaAI\adharaai\Data"
df = pd.read_csv(P + r"\adharaai_deployment_ready_v2.csv")
new = pd.read_csv(D + r"\claude_synthetic_batch_3.csv")

def chk(i, s):
    assert s in df.loc[i, "clause_text"], f"Row {i} text mismatch - stop and check indices"

# 1. Relabels: idx -> (text check, new clause_type, new risk_level or None)
edits = {
    13:  ("increased by 5%",               "payment",     None),
    15:  ("10% increment",                 "payment",     None),
    24:  ("PERIODIC REVISION",             "payment",     "medium"),
    37:  ("11 (Eleven) months from",       "payment",     None),
    26:  ("take position",                 "termination", "high"),
    75:  ("absolute right to access",      "access",      "high"),
    117: ("penal interest at 24%",         "penalty",     None),
}
for i, (s, t, r) in edits.items():
    chk(i, s)
    df.loc[i, "clause_type"] = t
    if r:
        df.loc[i, "risk_level"] = r

# 2. Row 140: rewrite as pure penalty (review this text)
chk(140, "unauthorized subletting")
df.loc[140, "clause_text"] = ("Any unauthorized subletting of the premises shall attract a penalty equal to "
                              "two months' rent and forfeiture of fifty percent of the security deposit.")
df.loc[140, "clause_type"] = "penalty"
df.loc[140, "simplified_text"] = ("If you sublet the premises without permission, you will pay a penalty of "
                                  "two months' rent and lose half of your security deposit.")
df.loc[140, "risk_reason"] = "Heavy fixed financial penalty for unauthorized subletting."

# 3. Show row 57 for review (not changed)
print("ROW 57:", df.loc[57, ["clause_type", "risk_level", "clause_text"]].to_dict())

# 4. Drop rows that fit none of the 8 classes
drop = {28: "DESIGNATION", 29: "DATE OF JOINING", 32: "Standard working hours",
        47: "makes no representation, warranty"}
for i, s in drop.items():
    chk(i, s)
df = df.drop(index=list(drop)).reset_index(drop=True)

# 5. Add batch 3, dedupe, save
df = pd.concat([df, new], ignore_index=True).drop_duplicates(subset="clause_text")
out = P + r"\adharaai_deployment_ready_v3.csv"
df.to_csv(out, index=False)
print(len(df), "rows saved to", out)
print(df["clause_type"].value_counts())
print(df["risk_level"].value_counts())

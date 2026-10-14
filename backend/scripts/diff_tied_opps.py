import pandas as pd

df = pd.read_excel('data/Renewals Summary 3.xlsx', sheet_name='Today_Data')
r1 = df[df['Opportunity ID 18 Digit'] == '006Qp00000YdMgGIAV'].iloc[0]
r2 = df[df['Opportunity ID 18 Digit'] == '006Qp00000eV7mAIAS'].iloc[0]

diffs = {}
for col in df.columns:
    v1 = r1[col]
    v2 = r2[col]
    if str(v1) != str(v2):
        diffs[col] = (v1, v2)

print("Differences between the two:")
for col, (v1, v2) in diffs.items():
    print(f"  {col}: {v1!r} vs {v2!r}")

import pandas as pd

wb = pd.ExcelFile('data/Renewals Summary 3.xlsx')
for sn in wb.sheet_names:
    df = wb.parse(sn)
    if 'Opportunity ID 18 Digit' in df.columns:
        c1 = (df['Opportunity ID 18 Digit'] == '006Qp00000eV7mAIAS').sum()
        c2 = (df['Opportunity ID 18 Digit'] == '006Qp00000YdMgGIAV').sum()
        print(f"Sheet {sn:25s}: eV7m={c1}, YdMg={c2}")

import pandas as pd

df_top = pd.read_excel('data/Renewals Summary 3.xlsx', sheet_name='Top 10 Region Summary')
na_top = df_top[df_top['Sub-Region'] == 'North America']
print("Top 10 Region Summary - North America:")
for _, r in na_top.iterrows():
    print(f"  {r['Opportunity ID 18 Digit']} | {r['Forecast ACV Amount']} | {r['Opportunity Name']}")

df_today = pd.read_excel('data/Renewals Summary 3.xlsx', sheet_name='Today_Data')
na_today = df_today[df_today['Sub-Region'] == 'North America']

print("\nWhere is 006Qp00000YdMgGIAV in Today_Data?")
y = na_today[na_today['Opportunity ID 18 Digit'] == '006Qp00000YdMgGIAV']
print("Found in Today_Data:", len(y))
print("Where is 006Qp00000YdMgGIAV in Top 10 Region Summary?")
y_top = df_top[df_top['Opportunity ID 18 Digit'] == '006Qp00000YdMgGIAV']
print("Found in Top 10 Region Summary:", len(y_top))

import pandas as pd

df = pd.read_excel('data/Renewals Summary 3.xlsx', sheet_name='Today_Data')
na = df[df['Sub-Region'] == 'North America'].copy()
print("Total NA in Today_Data:", len(na))
# Let's sort by Forecast ACV Amount descending with stable sort
na_sorted = na.sort_values('Forecast ACV Amount', ascending=False, kind='stable')
print("Top 12 from Today_Data sorted descending (stable):")
for i, (_, r) in enumerate(na_sorted.iloc[:12].iterrows(), 1):
    print(f"  #{i:2d}: {r['Opportunity ID 18 Digit']} | {r['Forecast ACV Amount']} | {r['Opportunity Name']}")

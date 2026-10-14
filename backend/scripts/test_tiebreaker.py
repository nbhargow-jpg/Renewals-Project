import pandas as pd

df = pd.read_excel('data/Renewals Summary 3.xlsx', sheet_name='Today_Data')
na = df[df['Sub-Region'] == 'North America']

# What if we sort by ACV descending with different tie-breakers?
# 1. ACV desc, then index:
s1 = na.sort_values(['Forecast ACV Amount'], ascending=[False], kind='stable')
print("s1 (index asc tie-breaker):")
print(s1.iloc[9:11][['Opportunity ID 18 Digit', 'Forecast ACV Amount']])

# 2. What if index desc?
s2 = na.sort_values(['Forecast ACV Amount'], ascending=[False]).sort_values(['Forecast ACV Amount'], ascending=[False], kind='mergesort')
# If we sort by index desc first, then ACV desc:
s3 = na.sort_index(ascending=False).sort_values('Forecast ACV Amount', ascending=False, kind='stable')
print("\ns3 (index desc tie-breaker):")
print(s3.iloc[9:11][['Opportunity ID 18 Digit', 'Forecast ACV Amount']])

# Phase 3 Progress

## Status key: ✅ done | 🔄 in-progress | ⬜ remaining

| Tab | Backend endpoint | Frontend page | API test | Status |
|-----|-----------------|---------------|----------|--------|
| Global shell (header + pill tabs) | n/a | AppShell + App.tsx | n/a | ⬜ |
| 1. Overview | /api/v2/overview/summary + /movements + /regional-breakdown | Dashboard.tsx | test_v2_overview.py | 🔄 |
| 2. Expiry | /api/v2/expiry/summary + /heatmap + /cell-detail | Expiry.tsx | test_v2_expiry.py | ⬜ |
| 3. Approval Funnel | /api/v2/approvals/distribution | Approvals.tsx | test_v2_approvals.py | ⬜ |
| 4. Business Unit | /api/v2/business-units/chart + /top-opportunities | BusinessUnits.tsx | test_v2_bu.py | ⬜ |
| 5. Region | /api/v2/regions/canonical + /{region}/summary + /{region}/movements + /{region}/opportunities | Regions.tsx | test_v2_regions.py | ⬜ |
| 6. Delayed Renewals | /api/v2/delayed-renewals/summary + /opportunities | DelayedRenewals.tsx (new) | test_v2_delayed.py | ⬜ |
| 7. Data | /api/v2/data/overview + /reconciliation + /cross-tab | Opportunities.tsx adapted | test_v2_data.py | ⬜ |
| Extras (History/Insights/Assistant) | existing | existing | n/a | ⬜ |

## Constants (from user, Oct-7 real data)
Q4 slice total: 348 deals, $40,068,990.09
- Commit: 308 / $30,349,636.71
- Best Case: 34 / $9,456,843.36  
- Pipeline: 1 / $49,737.62
- Blank: 5 / $212,772.40
- Closed: 0
Approval: Approved 96, Pending 6, Blank 246
Q4 yesterday (Oct-6): 346 / $39,592,770.91
Q4 last week (Sep-30): 334 / $39,164,857.76
FY2026 Commit->Closed vs yesterday: 3 deals / $345,891.08
Region Q4 counts: Europe 158, MENA 50, APAC 48, NAMR 37, South America 32, AFRICA 23

## Region mapping (EXACT value match)
Europe -> Europe
APAC -> APAC
AFRICA -> Africa
MENA -> Middle East and North Africa
NAMR -> North America
South America -> LATAM
(anything else -> Other, amber banner)

## Movement rule
Computed by diffing two SCOPED snapshots by Opportunity ID.
NOT from change_logs (unscoped, only yesterday, inflated for Q4).
Same logic as AnalyticsService._opps_for(snap) inner-join on opportunity_id_18.

## Amendments
- Blank category INCLUDED in totals (show as "Blank" column/card)
- Deleted/Lost INCLUDED by default; "Exclude D/L" toggle in header
- Slippage to 2027 = Q4 opps where close_date.year == 2027 (not 2026 -> 2027 movement)
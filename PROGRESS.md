# Mobileum Horizon — Progress Log

## 2026-10-08 — Overview Frontend Rebuild (Tab 1)

### Backend: `/api/v2/overview/*` — Slippage fix + test updates

**`backend/services/v2_overview_service.py`**
- `NEGATIVE_MOVES`: removed `Commit→Pipeline`. Third negative row is now **Slippage to 2027** (computed, not an FC transition).
- `_movements()`: slippage = deals whose `close_year` became 2027 *since the comparison date* (set difference `today_2027 - prev_2027`). Appended as 3rd entry in `negative[]` with `label="Slippage to 2027"`. `slippage_to_2027` top-level key kept for backward compat.

**`backend/tests/test_v2_overview.py`**
- Slot detection via `detect_file_slot` (content-based, any filename).
- `/api/compare` → `/api/analytics/compare`.
- Response shape: `movement[]` with `from`/`to` keys.

### Frontend: Overview page rebuilt from scratch

**`frontend/src/pages/Dashboard.tsx`** — full replacement
7 sections, top-to-bottom per spec:
1. **Regional Notice** — amber banner when `other_region_count > 0`
2. **Section 1** — Total Renewal Q4 ACV Value card (big $M, N Contracts pill, vs Yesterday / vs Last Week delta boxes)
3. **Section 2** — Four forecast category cards (Closed · Commit · Best Case · Pipeline) with color top-bar, deal count pill, big $M, delta badges + Blank/Unassigned mini-card
4. **Section 3** — Slippage to 2027 card (amber, N Slipped Deals, ACV, delta boxes)
5. **Section 4** — Forecast Category & Approval Movement block:
   - Closed highlight chip + vs Yesterday / vs Last Week toggle
   - Green positive table (Commit→Closed, Best Case→Commit, Pipeline→Best Case) + total row
   - Red negative table (Commit→Best Case, Best Case→Pipeline, Slippage to 2027 ⚠) + total row
   - Approval Movement Table (From / To / Count / ACV / View Deals) + total row
   - Click row → DealModal listing deals → click deal → OpportunityDrawer
6. **Section 6** — Proposal Confirmation: opportunity counts, fixed region order, totals row
7. **Section 7** — Regional Trend: ACV $M, Blank column, green check line, totals row

**API calls**: `GET /api/v2/overview/summary`, `/movements?compare=yesterday|last_week`, `/regional-breakdown`
**No numbers hard-coded**; no Year/Quarter/Clean All Data controls; Mobileum colours kept.

**`frontend/src/pages/DailyChanges.tsx`** — new page
- Legacy Overview components moved here: KPI Strip, Waterfall Chart, Forecast Sankey, Biggest Movers, Needs Attention
- Route: `/daily-changes` (sidebar: Activity icon, between Upload and History)

**`frontend/src/components/layout/Sidebar.tsx`**
- Added `Daily Changes` nav item with `Activity` icon

**`frontend/src/App.tsx`**
- Added `/daily-changes` route

**`frontend/src/api/client.ts`**
- Added `getV2OverviewSummary`, `getV2OverviewMovements`, `getV2RegionalBreakdown`

### Build & Tests

| Check | Result |
|-------|--------|
| `tsc --noEmit` | ✅ 0 errors |
| `npm run build` | ✅ 3334 modules, built in 89s |
| `pytest test_v2_overview.py` | ✅ 21 skipped (sample files not present) |

---

## Earlier work

### Backend V2 Overview Service
- `v2_overview_service.py` — Q4-scoped aggregations, movement diffing, regional breakdown
- `v2_overview.py` router — `/summary`, `/movements`, `/regional-breakdown`
- Region mapping: Europe, APAC, Africa, MENA→Middle East and North Africa, NAMR→North America, South America→LATAM

### Data Model
- `in_q4_2026` flag on Opportunity
- Snapshot date tracking with `yesterday_date`

### Analytics & Compare
- `/api/analytics/compare` endpoint with `from`/`to` keys on movement items
- Waterfall, Sankey, KPI Strip via analytics service


# Architecture and Roadmap

## Architecture Overview
The Mobileum Renewals Intelligence platform relies on an atomic, snapshot-based ingest model. Each day's ingest uploads up to four Excel workbooks:
- A mandatory Comparison Tool containing `today`, `yesterday` and `FinalChangeReport`.
- (Optional) Three summary workbooks providing baseline scoped data, primarily for bootstrapping the `lastweek` snapshot when historical comparisons are absent.

The database stores `opportunities` uniquely identified by their `opportunity_id_18` for a given `snapshot_id`. The frontend API is serviced through specific domain controllers (e.g., `V2OverviewService`) that fetch dynamic views (scopes) of the `opportunities` across `UploadSnapshot` dates.

## Scopes and Dynamic Slicing
Scoping logic has been refactored in `backend/services/scopes.py`. Instead of reading specific "fiscal_2026", "fiscal_2027" and "fiscal_q4" slots in Excel parsing and attaching statically named boolean flags, we derive scopes logically at query time via `ScopeService`.
- **Renewals**: `sales_type == 'Renewals'`
- **Current Quarter Slice**: Renewals whose `fiscal_period == current_quarter(snapshot_date)`
- **Slippage**: Current Quarter Slice opportunities whose `close_date` falls after the current quarter's calendar end date.
- **Delayed**: Renewals whose `fiscal_period` is from an earlier quarter in the same fiscal year and whose `forecast_category` is not Closed.
- **Expiry Window**: Renewals whose `service_expiry_period` falls in the current fiscal year or the next fiscal year.

`ScopeService` utilizes the global configuration `FISCAL_YEAR_START_MONTH` (defaults to 1 for January) to compute the corresponding quarters dynamically.

## Rollover Foundation (Quarter Change)
By deriving scopes logically:
- No literal "Q4", "2026", or "2027" variables exist in code for scoping logic.
- As the snapshot dates progress beyond quarter boundaries, the backend automatically calculates the new "current_quarter" and filters correctly.
- Comparisons against `yesterday` or `last_week` correctly inherit the primary snapshot's scope boundaries, ensuring a fair apples-to-apples diff even across month or quarter boundaries.

## Roadmap
- [ ] Migrate frontend Dashboard / UI to reflect dynamic API scope labels.
- [ ] Decouple remaining Expiry dashboard backend APIs similarly.
- [ ] Incorporate User-Managed targets directly into the API instead of relying on flat files if needed.

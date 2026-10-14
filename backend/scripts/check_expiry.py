import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.models.opportunity import Opportunity
from sqlalchemy import func

db = SessionLocal()
snap_id = "fa645753-1b9c-40b7-bdf4-4ebf08244ea3"
exp_periods = db.query(
    Opportunity.service_expiry_period, 
    func.count(Opportunity.id), 
    func.sum(Opportunity.forecast_acv_amount)
).filter(Opportunity.snapshot_id == snap_id).group_by(Opportunity.service_expiry_period).all()

print("Service Expiry Periods in snapshot 2026-10-06:")
for ep in sorted(exp_periods, key=lambda x: str(x[0])):
    print(f"  {ep[0]}: count={ep[1]}, acv={float(ep[2] or 0):,.2f}")

# And check Q3 or 2026 quarters:
q_periods = ['Q1-2026', 'Q2-2026', 'Q3-2026', 'Q4-2026']
tot_q_acv = db.query(func.sum(Opportunity.forecast_acv_amount)).filter(
    Opportunity.snapshot_id == snap_id,
    Opportunity.service_expiry_period.in_(q_periods)
).scalar()
tot_q_cnt = db.query(func.count(Opportunity.id)).filter(
    Opportunity.snapshot_id == snap_id,
    Opportunity.service_expiry_period.in_(q_periods)
).scalar()
print(f"\n2026 Quarters (Q1-Q4): count={tot_q_cnt}, acv={float(tot_q_acv or 0):,.2f}")

# What quarters make up 120,511,647.51 and 1,167?
# Let's check slide 2's exact table from inspect_pptx or pptx_structure.txt!
db.close()

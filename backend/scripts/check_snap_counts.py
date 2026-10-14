import sqlite3
import pandas as pd

conn = sqlite3.connect('renewals.db')
snaps = pd.read_sql_query('SELECT id, label, snapshot_date, is_active_today FROM upload_snapshots', conn)
print(snaps)
for _, s in snaps.iterrows():
    c = pd.read_sql_query(f"SELECT count(*) as cnt FROM opportunities WHERE snapshot_id = '{s['id']}' AND forecast_category = 'Commit'", conn)
    c_app = pd.read_sql_query(f"SELECT count(*) as cnt FROM opportunities WHERE snapshot_id = '{s['id']}' AND approval_status = 'Approved'", conn)
    c_na = pd.read_sql_query(f"SELECT count(*) as cnt FROM opportunities WHERE snapshot_id = '{s['id']}' AND sub_region = 'North America'", conn)
    print(f"Snapshot: {s['label']} ({s['snapshot_date']}) -> Commit: {c.iloc[0]['cnt']} | Approved: {c_app.iloc[0]['cnt']} | NA: {c_na.iloc[0]['cnt']}")

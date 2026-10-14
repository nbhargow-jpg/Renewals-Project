import subprocess
import time
from pathlib import Path

shots = [
    ("http://localhost:5173/regions", "light", "screenshots/regions_light_1440.png"),
    ("http://localhost:5173/regions", "dark", "screenshots/regions_dark_1440.png"),
    ("http://localhost:5173/opportunities", "light", "screenshots/explore_light_1440.png"),
    ("http://localhost:5173/opportunities", "dark", "screenshots/explore_dark_1440.png"),
    ("http://localhost:5173/history", "light", "screenshots/history_light_1440.png"),
    ("http://localhost:5173/history", "dark", "screenshots/history_dark_1440.png"),
]

for url, scheme, out in shots:
    cmd = [
        "npx", "playwright", "screenshot",
        "--channel=msedge",
        '--viewport-size=1440, 900',
        f"--color-scheme={scheme}",
        "--wait-for-timeout=2500",
        url,
        out,
    ]
    print(f"Capturing {out} ({scheme})...")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error capturing {out}: {res.stderr}")
    else:
        p = Path(out)
        print(f"Success: {out} ({p.stat().st_size:,} bytes)")

print("\nAll screenshot tasks finished.")

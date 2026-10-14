import subprocess
import time
from pathlib import Path

chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not Path(chrome_path).exists():
    chrome_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

out_path = r"C:\Users\RISHITHA\Downloads\Renewal_Data\screenshots\history_light_1440.png"
cmd = [
    chrome_path,
    "--headless=new",
    "--disable-gpu",
    "--window-size=1440,900",
    "--virtual-time-budget=3000",
    f"--screenshot={out_path}",
    "http://localhost:5173/history",
]

print("Running command:", " ".join(cmd))
res = subprocess.run(cmd, capture_output=True, text=True)
print("Returncode:", res.returncode)
print("Stdout:", res.stdout)
print("Stderr:", res.stderr)

p = Path(out_path)
if p.exists():
    print(f"Screenshot size: {p.stat().st_size:,} bytes")

import json
from pathlib import Path

transcript_path = Path(r"C:\Users\RISHITHA\.gemini\antigravity-ide\brain\cabce88f-f571-4b4f-a41d-73e5cdf3b372\.system_generated\logs\transcript_full.jsonl")

if transcript_path.exists():
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for line in f:
            if 'capture_browser_console_logs' in line or 'CONSOLE' in line:
                data = json.loads(line)
                print("Found log entry:", str(data)[:500])
else:
    print("Transcript not found")

import json
from pathlib import Path

transcript_path = Path(r"C:\Users\RISHITHA\.gemini\antigravity-ide\brain\cabce88f-f571-4b4f-a41d-73e5cdf3b372\.system_generated\logs\transcript_full.jsonl")

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        obj = json.loads(line)
        if obj.get('step_index') == 1397:
            content = obj.get('content', '')
            idx = content.find("129: capture_browser_console_logs")
            if idx != -1:
                print(content[idx:idx+2000])

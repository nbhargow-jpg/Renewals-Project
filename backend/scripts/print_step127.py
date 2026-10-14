import json
from pathlib import Path

transcript_path = Path(r"C:\Users\RISHITHA\.gemini\antigravity-ide\brain\cabce88f-f571-4b4f-a41d-73e5cdf3b372\.system_generated\logs\transcript_full.jsonl")

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        obj = json.loads(line)
        if obj.get('step_index') == 1397:
            content = obj.get('content', '')
            for part in content.split("### Step "):
                num = part.split(":")[0].strip()
                if num == "127":
                    print("=== STEP 127 (read_browser_page) ===")
                    print(part)
                elif num == "129":
                    print("=== STEP 129 (console logs) ===")
                    print(part)

import json
from pathlib import Path

transcript_path = Path(r"C:\Users\RISHITHA\.gemini\antigravity-ide\brain\cabce88f-f571-4b4f-a41d-73e5cdf3b372\.system_generated\logs\transcript_full.jsonl")

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        obj = json.loads(line)
        if obj.get('step_index') == 1397:
            # this is the subagent response
            content = obj.get('content', '')
            for part in content.split("### Step "):
                if "console_logs" in part or "Error" in part or "Step 129" in part or "Step 131" in part:
                    print("--- STEP ---")
                    print(part[:1500])

from pathlib import Path

logs_dir = Path(r"C:\Users\RISHITHA\.gemini\antigravity-ide\brain")
for p in logs_dir.rglob("*.jsonl"):
    if "cabce88f" in str(p) and p.name == "transcript.jsonl":
        with open(p, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                if "console" in line.lower() or "error" in line.lower():
                    print(line[:300])

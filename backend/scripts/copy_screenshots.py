import shutil
from pathlib import Path

brain_dir = Path(r"C:\Users\RISHITHA\.gemini\antigravity-ide\brain\cabce88f-f571-4b4f-a41d-73e5cdf3b372")
dest_dir = Path(r"C:\Users\RISHITHA\Downloads\Renewal_Data\screenshots")
dest_dir.mkdir(parents=True, exist_ok=True)

copies = {
    "regions_light_1440": "regions_light_1440.png",
    "regions_dark_1440": "regions_dark_1440.png",
    "explore_light_1440": "explore_light_1440.png",
    "explore_dark_1440": "explore_dark_1440.png",
    "history_light_1440": "history_light_1440.png",
    "history_dark_1440": "history_dark_1440.png",
}

for prefix, dest_name in copies.items():
    # find newest matching file
    matches = sorted(brain_dir.glob(f"{prefix}*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    if matches:
        src = matches[0]
        dest = dest_dir / dest_name
        shutil.copy2(src, dest)
        print(f"Copied {src.name} -> {dest.name} ({dest.stat().st_size} bytes)")
    else:
        print(f"WARNING: No file found matching {prefix}")

print("\nFiles now in screenshots directory:")
for f in sorted(dest_dir.glob("*.png")):
    print(f" - {f.name} ({f.stat().st_size:,} bytes)")

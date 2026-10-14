with open('frontend/src/pages/Expiry.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

target = '{sum.categories.map((c: string) => {'
replacement = '{sum.categories.filter((c: string) => c !== "Pipeline").map((c: string) => {'
if target in text:
    text = text.replace(target, replacement)
    with open('frontend/src/pages/Expiry.tsx', 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print("Expiry patched")
else:
    print("Target not found")

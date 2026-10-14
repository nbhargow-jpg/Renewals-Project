with open('frontend/src/pages/Approvals.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

target = '<span>{seg.status}</span>'
rep = "<span>{seg.status === 'Blank' ? 'Not submitted' : seg.status}</span>"
if target in text:
    text = text.replace(target, rep)

# Also ensure CompactGrid columns filters out Pipeline
text = text.replace("columns={categories}", "columns={categories.filter((c: string) => c !== 'Pipeline')}")

with open('frontend/src/pages/Approvals.tsx', 'w', encoding='utf-8', newline='\n') as f:
    f.write(text)
print("Approvals updated successfully")

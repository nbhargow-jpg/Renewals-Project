with open('frontend/src/pages/Delayed.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace("api.get('/api/v2/delayed/summary'", "api.get('/v2/delayed/summary'")
text = text.replace("api.get('/api/v2/delayed/deals'", "api.get('/v2/delayed/deals'")

with open('frontend/src/pages/Delayed.tsx', 'w', encoding='utf-8', newline='\n') as f:
    f.write(text)

print("Delayed URLs fixed")

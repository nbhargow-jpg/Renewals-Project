import ast
with open('backend/services/analytics_service.py', encoding='utf-8') as f:
    node = ast.parse(f.read())
for n in node.body:
    if isinstance(n, ast.ClassDef):
        print(f"Class {n.name}:")
        for item in n.body:
            if isinstance(item, ast.FunctionDef):
                print(f"  - {item.name}")

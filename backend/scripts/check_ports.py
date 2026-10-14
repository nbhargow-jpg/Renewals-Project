import urllib.request

for port in [5173, 5174, 8000]:
    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        print(f"Port {port}: UP (status {req.status})")
    except Exception as e:
        print(f"Port {port}: DOWN ({e})")

import json
with open(r'C:\Dev\rbgg\documentation\fof\test-output6.json') as f:
    records = json.load(f)
for r in records:
    print(f"{r['image']['filename']:30s} -> {r['category']:8s}/{r['subtype']:8s} conf={r['image']['confidence']:5.3f} method={r['classification']['method']} country={r['country']}")
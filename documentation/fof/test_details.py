import json
with open(r'C:\Dev\rbgg\documentation\fof\test-output6.json') as f:
    records = json.load(f)
for r in records:
    fn = r['image']['filename']
    if fn in ('1_1 3 step.png', '2PARA LAT Cas 2.png', 'VC LAT Asslt Team.png', '1ATF 10-2b.jpg'):
        print(f"=== {fn} ===")
        print(f"  category={r['category']}, subtype={r['subtype']}")
        print(f"  country={r['country']}")
        print(f"  unit_details={json.dumps(r.get('unit_details'), indent=4)}")
        print(f"  marker_details={json.dumps(r.get('marker_details'), indent=4)}")
        print()
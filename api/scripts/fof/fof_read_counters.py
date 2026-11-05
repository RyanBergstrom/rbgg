import json
path = r'C:\Dev\rbgg\api\configs\fof\counters.json'
with open(path) as f:
    data = json.load(f)
print('Type:', type(data))
print('Count:', len(data))
if data:
    first = data[0]
    print('Keys:', list(first.keys()))
    print('ID:', first.get('id', 'N/A'))
    print('Category:', first.get('category', 'N/A'))
    print('Subtype:', first.get('subtype', 'N/A'))
    print('Country:', first.get('country', 'N/A'))
    print('Image keys:', list(first.get('image', {}).keys()) if first.get('image') else 'N/A')
    # Check for some common property names
    for key in ['unit_details', 'marker_details', 'combat', 'assets', 'status']:
        if key in first:
            print(f'{key}: present (type: {type(first[key]).__name__})')
        else:
            print(f'{key}: absent')
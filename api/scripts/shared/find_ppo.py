import os
base = 'C:/Dev/rbgg'
found = []
for root, dirs, files in os.walk(base):
    for f in files:
        if 'twilight' in f.lower() and 'ppo' in f.lower():
            found.append(os.path.join(root, f))
for path in sorted(found):
    print(path)
print(f"Total: {len(found)}")
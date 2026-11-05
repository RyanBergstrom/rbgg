import os
runtime_dir = 'runtime'
if os.path.exists(runtime_dir):
    files = [f for f in os.listdir(runtime_dir) if 'twilight' in f]
    for f in sorted(files):
        print(f)
else:
    print("Directory doesn't exist")
"""Create the input file: one random integer per line, like data1.set on the cluster."""
import os
import random
import sys

count = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), 'shared', 'data1.set')

os.makedirs(os.path.dirname(out), exist_ok=True)
rng = random.Random(42)  # fixed seed so every run sorts the same data
with open(out, 'w') as f:
    for _ in range(count):
        f.write(f"{rng.randint(-2**31, 2**31 - 1)}\n")
print(f"Wrote {count:,} random 32-bit integers to {out}")

"""
sweep_difficulty.py -- disclosure of the difficulty setting used in the report.

CENTRE_SCALE controls how far apart the four document categories sit in feature
space, so it sets how hard the detection problem is. The report uses 0.50.

This script re-runs the whole comparison across a wide range so a reader can
check two things for themselves:
  1. whether the ordering of the methods depends on that choice, and
  2. how much of the reported baseline forgetting is an artefact of it.

Both answers are reported in the paper, including the unflattering one:
0.50 is close to the setting that maximises the baseline's forgetting, and
above about 1.0 the forgetting problem largely disappears.

Run: python3 sweep_difficulty.py   (writes sweep_results.json)
"""
import importlib.util, json
import numpy as np

spec = importlib.util.spec_from_file_location("m", "fcl_sim.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

METHODS = ["fedavg", "ewc", "replay", "breadcrumbs", "joint"]
out = {}
print(f"{'CS':>5s} " + "  ".join(f"{x:>13s}" for x in METHODS) + "     (ACC / FGT)")
for cs in [0.30, 0.40, 0.50, 0.60, 0.80, 1.00, 1.50]:
    m.CENTRE_SCALE = cs
    row, cells = {}, []
    for meth in METHODS:
        mats = [m.run_method(meth, s) for s in m.SEEDS]
        ms = np.array([m.metrics(x) for x in mats])
        row[meth] = {"ACC": round(float(ms[:, 0].mean()) * 100, 1),
                     "FGT": round(float(ms[:, 2].mean()) * 100, 1)}
        cells.append(f"{row[meth]['ACC']:5.1f}/{row[meth]['FGT']:5.1f}")
    out[str(cs)] = row
    print(f"{cs:5.2f} " + "  ".join(f"{c:>13s}" for c in cells))

json.dump(out, open("sweep_results.json", "w"), indent=2)
print("\nWrote sweep_results.json")

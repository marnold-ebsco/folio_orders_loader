import collections
import os
import sys

REPO = "/home/marnold/scratch/EBSCOnet"
sys.path.insert(0, REPO)
os.chdir(REPO)

from pipeline.ebsconet_prep import load_config, read_sops, classify, enrich  # noqa: E402

cfg = load_config("ebsconet_config.json")
for kind in ("electronic", "physical", "P-E"):
    _, rows = read_sops(
        f"out/three_type_test/filled/TestEBSCOnet_for_customer_{kind}.xlsx")
    cnt = collections.Counter()
    first = {}
    multi = collections.Counter(r["Order Number"] for r in rows)
    for i, r in enumerate(rows):
        route, why = classify(r, cfg)
        if route is None:
            cnt["excluded"] += 1
            continue
        out, _ = enrich(r, route, cfg)
        key = (route, out["FOLIO Order Type"])
        cnt[key] += 1
        first.setdefault(key, i)
    print(kind, dict(cnt), "first idx", first)
    print("  multi-line orders:",
          [(k, v) for k, v in multi.items() if v > 1][:5])

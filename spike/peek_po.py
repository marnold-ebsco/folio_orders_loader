import json
import os
import sys

REPO = "/home/marnold/scratch/EBSCOnet"
sys.path.insert(0, REPO)
os.chdir(REPO)

from pipeline.folio_common import connect  # noqa: E402

client = connect("sunflower_bugfest.ini")
po = client.folio_get("/orders/composite-orders/" + sys.argv[1])
line = po["compositePoLines"][0]
print("ongoing:", json.dumps(po.get("ongoing")))
print("poLineNumber:", line.get("poLineNumber"))
print("details:", json.dumps(line.get("details")))
print("cost:", json.dumps(line.get("cost")))

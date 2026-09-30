"""Spike: build one composite order from an enriched EBSCONET row and POST it.

Dry run by default (prints the payload). Use --live to POST to the tenant.

    cd ~/scratch/EBSCOnet
    .venv/bin/python ~/scratch/folio_orders/spike_one_po.py --ini sunflower_bugfest.ini
"""
import argparse
import json
import os
import re
import sys

REPO = "/home/marnold/scratch/EBSCOnet"
sys.path.insert(0, REPO)
os.chdir(REPO)

from pipeline.ebsconet_prep import (  # noqa: E402
    classify, enrich, load_config, read_sops)
from pipeline.folio_common import connect  # noqa: E402

FILLED = "out/three_type_test/filled/TestEBSCOnet_for_customer_{}.xlsx"
FILES = {"online": "electronic", "print": "physical", "pe": "P-E"}
FORMAT = {"online": "Electronic Resource", "print": "Physical Resource",
          "pe": "P/E Mix"}


def q(text):
    return '"%s"' % text


def one(client, path, key, query):
    hits = client.folio_get(path, key=key,
                            query_params={"query": query, "limit": 5})
    if not hits:
        raise SystemExit(f"lookup failed: {path} {query}")
    return hits[0]


def lookups(client, cfg, row):
    f = cfg["folio"]
    loc_code = None
    if row.get("FOLIO Location"):
        m = re.search(r"\(([^)]+)\)\s*$", row["FOLIO Location"])
        loc_code = m.group(1) if m else row["FOLIO Location"]
    ids = {
        "vendor": one(client, "/organizations/organizations",
                      "organizations",
                      "code==" + q(f["vendor_org_code"]))["id"],
        "acq": one(client, "/orders/acquisition-methods",
                   "acquisitionMethods",
                   "value==" + q(f["acquisition_method"]))["id"],
        "fund": one(client, "/finance/funds", "funds",
                    "code==" + q(row["FOLIO Fund"])),
        "xclass": one(client, "/finance/expense-classes", "expenseClasses",
                      "code==" + q(row["FOLIO Expense Class"]))["id"],
    }
    if loc_code:
        ids["loc"] = one(client, "/locations", "locations",
                         "code==" + q(loc_code))["id"]
        ids["mtype"] = one(client, "/material-types", "mtypes",
                           "name==" + q(row["FOLIO Material Type"]))["id"]
    ids["idtype"] = {
        n: one(client, "/identifier-types", "identifierTypes",
               "name==" + q(n))["id"]
        for n in ("ISSN", f["title_number_type"])}
    return ids


def build_order(po, row, route, ids, cfg):
    cost = float(row["Total Cost"])
    line = {
        "titleOrPackage": row["Title Name"],
        "acquisitionMethod": ids["acq"],
        "orderFormat": FORMAT[route],
        "source": "User",
        "checkinItems": False,
        "cancellationRestriction": row["Cancellation Restriction"] == "true",
        "fundDistribution": [{
            "fundId": ids["fund"]["id"], "code": ids["fund"]["code"],
            "expenseClassId": ids["xclass"],
            "distributionType": "percentage", "value": 100}],
        "details": {
            "subscriptionFrom": row["Start Date"],
            "subscriptionTo": row["Expiration Date"],
            "productIds": [{
                "productId": row["Title Number"],
                "productIdType": ids["idtype"][cfg["folio"]["title_number_type"]],
            }],
        },
        "cost": {"currency": row["Currency"]},
        "publisher": row["Publisher Name"],
    }
    if route in ("online", "pe"):
        line["cost"].update(listUnitPriceElectronic=cost, quantityElectronic=1)
        line["eresource"] = {
            "createInventory": "None", "accessProvider": ids["vendor"],
            "activated": False}
    if route in ("print", "pe"):
        line["cost"].update(listUnitPrice=cost, quantityPhysical=1)
        line["physical"] = {"createInventory": "None"}
    if "loc" in ids:
        line["locations"] = [{
            "locationId": ids["loc"],
            "quantityPhysical": 1 if route in ("print", "pe") else 0,
            "quantityElectronic": 1 if route in ("online", "pe") else 0}]
    ongoing = row["FOLIO Order Type"] == "Ongoing"
    order = {
        "poNumber": po, "vendor": ids["vendor"],
        "orderType": "Ongoing" if ongoing else "One-Time",
        "workflowStatus": "Pending",
        "compositePoLines": [line],
    }
    if ongoing:
        order["ongoing"] = {
            "interval": int(row["FOLIO Renewal Interval (Days)"]),
            "isSubscription": True, "manualRenewal": False,
            "renewalDate": row["Expiration Date"]}
    return order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ini", required=True)
    ap.add_argument("--kind", choices=list(FILES), default="online")
    ap.add_argument("--row", type=int, default=0)
    ap.add_argument("--also", type=int, nargs="*", default=[],
                    help="extra row indexes added as more lines on the PO")
    ap.add_argument("--po", default="SPIKE1")
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()

    cfg = load_config("ebsconet_config.json")
    _, rows = read_sops(FILLED.format(FILES[a.kind]))
    row = rows[a.row]
    route, why = classify(row, cfg)
    if route is None:
        raise SystemExit(f"row excluded: {why}")
    row, warns = enrich(row, route, cfg)
    client = connect(a.ini)
    order = build_order(a.po, row, route, lookups(client, cfg, row), cfg)
    for idx in a.also:
        r2 = rows[idx]
        route2, why = classify(r2, cfg)
        if route2 is None:
            raise SystemExit(f"row {idx} excluded: {why}")
        r2, _ = enrich(r2, route2, cfg)
        extra = build_order(a.po, r2, route2, lookups(client, cfg, r2), cfg)
        order["compositePoLines"] += extra["compositePoLines"]
    print(json.dumps(order, indent=2))
    if not a.live:
        print("\nDRY RUN - nothing posted (use --live)")
        return
    exists = client.folio_get("/orders/composite-orders", key="purchaseOrders",
                              query_params={"query": "poNumber==" + q(a.po)})
    if exists:
        raise SystemExit(f"PO {a.po} already exists; not posting")
    res = client.folio_post("/orders/composite-orders", order)
    print("CREATED", res["id"], res["poNumber"], res["workflowStatus"])
    for ln in res["compositePoLines"]:
        print("  line", ln["poLineNumber"], ln["orderFormat"])


if __name__ == "__main__":
    main()

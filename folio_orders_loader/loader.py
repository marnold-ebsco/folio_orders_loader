"""Load grouped PO records: skip existing POs, dry run unless live."""
from .builder import build_order
from .lookups import LookupError_, Resolver
from .records import group_by_po


def po_exists(client, po_number):
    hits = client.folio_get(
        "/orders/composite-orders", key="purchaseOrders",
        query_params={"query": 'poNumber=="%s"' % po_number, "limit": 1})
    return bool(hits)


def load(client, lines, live=False):
    """Load line records. Returns a list of (po_number, status, detail).

    Status is one of: invalid, exists, lookup-failed, dry-run, created, error.
    Re-running is safe: POs that already exist are skipped.
    """
    resolver = Resolver(client)
    pos, problems = group_by_po(lines)
    results = []
    for po, group in pos.items():
        if po in problems:
            results.append((po, "invalid", "; ".join(problems[po])))
            continue
        if po_exists(client, po):
            results.append((po, "exists", ""))
            continue
        try:
            order = build_order(po, group, resolver)
        except LookupError_ as exc:
            results.append((po, "lookup-failed", str(exc)))
            continue
        if not live:
            results.append((po, "dry-run", f"{len(group)} line(s)"))
            continue
        try:
            created = client.folio_post("/orders/composite-orders", order)
        except Exception as exc:  # FOLIO validation errors, network errors
            results.append((po, "error", str(exc)[:500]))
            continue
        nums = ",".join(ln["poLineNumber"]
                        for ln in created["compositePoLines"])
        results.append((po, "created", nums))
    return results

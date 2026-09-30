"""Build a composite-order payload from grouped line records."""


def build_line(line, r):
    fmt = line["order_format"]
    electronic = fmt in ("Electronic Resource", "P/E Mix")
    physical = fmt in ("Physical Resource", "P/E Mix")
    cost = float(line["cost"])
    fund = r.fund(line["fund_code"])

    details = {}
    ids = [{"productId": p["value"],
            "productIdType": r.identifier_type(p["type"])}
           for p in line.get("product_ids") or [] if p.get("value")]
    if ids:
        details["productIds"] = ids
    if line.get("subscription_from"):
        details["subscriptionFrom"] = line["subscription_from"]
    if line.get("subscription_to"):
        details["subscriptionTo"] = line["subscription_to"]

    price = {"currency": line["currency"]}
    if electronic:
        price.update(listUnitPriceElectronic=cost, quantityElectronic=1)
    if physical:
        price.update(listUnitPrice=cost, quantityPhysical=1)

    out = {
        "titleOrPackage": line["title"],
        "acquisitionMethod": r.acquisition_method(line["acquisition_method"]),
        "orderFormat": fmt,
        "source": "User",
        "checkinItems": False,
        "cancellationRestriction": bool(line.get("cancellation_restriction")),
        "fundDistribution": [{
            "fundId": fund["id"], "code": fund["code"],
            "expenseClassId": r.expense_class(line["expense_class_code"]),
            "distributionType": "percentage", "value": 100}],
        "cost": price,
    }
    if details:
        out["details"] = details
    if line.get("publisher"):
        out["publisher"] = line["publisher"]
    if electronic:
        out["eresource"] = {
            "createInventory": "None", "activated": False,
            "accessProvider": r.organization(
                line.get("access_provider_code") or line["vendor_code"])}
    if physical:
        out["physical"] = {"createInventory": "None"}
        out["physical"]["materialType"] = r.material_type(line["material_type"])
    if line.get("location_code"):
        out["locations"] = [{
            "locationId": r.location(line["location_code"]),
            "quantityPhysical": 1 if physical else 0,
            "quantityElectronic": 1 if electronic else 0}]
    return out


def renewal_date(lines):
    """Latest subscription_to across the lines, if any."""
    dates = [ln["subscription_to"] for ln in lines if ln.get("subscription_to")]
    return max(dates) if dates else None


def build_order(po_number, lines, r):
    first = lines[0]
    order = {
        "poNumber": str(po_number),
        "vendor": r.organization(first["vendor_code"]),
        "orderType": first["order_type"],
        "workflowStatus": "Pending",
        "compositePoLines": [build_line(ln, r) for ln in lines],
    }
    if first["order_type"] == "Ongoing":
        ongoing = {
            "interval": int(first["interval_days"]),
            "isSubscription": bool(first.get("is_subscription", True)),
            "manualRenewal": bool(first.get("manual_renewal", False)),
        }
        date = first.get("renewal_date") or renewal_date(lines)
        if date:
            ongoing["renewalDate"] = date
        order["ongoing"] = ongoing
    return order

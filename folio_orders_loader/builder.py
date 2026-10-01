"""Build a composite-order payload from grouped line records."""
from .records import fund_list, location_list, quantities


def build_line(line, r):
    fmt = line["order_format"]
    electronic = fmt in ("Electronic Resource", "P/E Mix")
    physical = fmt in ("Physical Resource", "P/E Mix")
    cost = float(line["cost"])
    qty_physical, qty_electronic = quantities(line)
    distribution = []
    for f in fund_list(line):
        fund = r.fund(f["code"])
        distribution.append({
            "fundId": fund["id"], "code": fund["code"],
            "expenseClassId": r.expense_class(f["expense_class_code"]),
            "distributionType": f["type"], "value": float(f["value"])})

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
        price.update(listUnitPriceElectronic=cost,
                     quantityElectronic=qty_electronic)
    if physical:
        price.update(listUnitPrice=cost, quantityPhysical=qty_physical)
    if line.get("discount") not in (None, ""):
        price["discount"] = float(line["discount"])
        price["discountType"] = line.get("discount_type") or "amount"
    if line.get("additional_cost") not in (None, ""):
        price["additionalCost"] = float(line["additional_cost"])
    if line.get("exchange_rate") not in (None, ""):
        price["exchangeRate"] = float(line["exchange_rate"])

    out = {
        "titleOrPackage": line["title"],
        "acquisitionMethod": r.acquisition_method(line["acquisition_method"]),
        "orderFormat": fmt,
        "source": "User",
        "checkinItems": False,
        "cancellationRestriction": bool(line.get("cancellation_restriction")),
        "fundDistribution": distribution,
        "cost": price,
    }
    if details:
        out["details"] = details
    if line.get("publisher"):
        out["publisher"] = line["publisher"]
    if line.get("edition"):
        out["edition"] = line["edition"]
    if line.get("publication_date"):
        out["publicationDate"] = str(line["publication_date"])
    contributors = [{"contributor": c["name"],
                     "contributorNameTypeId": r.contributor_name_type(c["type"])}
                    for c in line.get("contributors") or []]
    if contributors:
        out["contributors"] = contributors
    if line.get("description"):
        out["poLineDescription"] = line["description"]
    if line.get("receipt_status"):
        out["receiptStatus"] = line["receipt_status"]
    if line.get("payment_status"):
        out["paymentStatus"] = line["payment_status"]
    vendor_detail = {}
    if line.get("vendor_reference_number"):
        vendor_detail["referenceNumbers"] = [{
            "refNumber": line["vendor_reference_number"],
            "refNumberType": line["vendor_reference_type"]}]
    if line.get("vendor_account"):
        vendor_detail["vendorAccount"] = line["vendor_account"]
    if vendor_detail:
        out["vendorDetail"] = vendor_detail
    if electronic:
        out["eresource"] = {
            "createInventory": "None", "activated": False,
            "accessProvider": r.organization(
                line.get("access_provider_code") or line["vendor_code"])}
    if physical:
        out["physical"] = {"createInventory": "None"}
        out["physical"]["materialType"] = r.material_type(line["material_type"])
    locations = location_list(line)
    if locations:
        out["locations"] = [{
            "locationId": r.location(loc["code"]),
            "quantityPhysical": loc["quantity_physical"],
            "quantityElectronic": loc["quantity_electronic"]}
            for loc in locations]
    return out


def renewal_date(lines):
    """Latest subscription_to across the lines, if any."""
    dates = [ln["subscription_to"] for ln in lines if ln.get("subscription_to")]
    return max(dates) if dates else None


def as_list(value):
    """A list as is, or a '|'-separated string split into non-empty trimmed items."""
    if isinstance(value, str):
        value = value.split("|")
    return [str(v).strip() for v in value or [] if str(v).strip()]


def build_order(po_number, lines, r):
    first = lines[0]
    order = {
        "poNumber": str(po_number),
        "vendor": r.organization(first["vendor_code"]),
        "orderType": first["order_type"],
        "workflowStatus": "Pending",
        "compositePoLines": [build_line(ln, r) for ln in lines],
    }
    notes = as_list(first.get("notes"))
    if notes:
        order["notes"] = notes
    tags = as_list(first.get("tags"))
    if tags:
        order["tags"] = {"tagList": tags}
    if first.get("bill_to"):
        order["billTo"] = first["bill_to"]
    if first.get("ship_to"):
        order["shipTo"] = first["ship_to"]
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

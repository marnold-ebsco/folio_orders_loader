"""Build a composite-order payload from grouped line records."""
from .records import LINE_FLAGS, LINE_UUIDS, fund_list, location_list, quantities


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
    ids = []
    for p in line.get("product_ids") or []:
        if p.get("value"):
            pid = {"productId": p["value"],
                   "productIdType": r.identifier_type(p["type"])}
            if p.get("qualifier"):
                pid["qualifier"] = p["qualifier"]
            ids.append(pid)
    if ids:
        details["productIds"] = ids
    if line.get("receiving_note"):
        details["receivingNote"] = line["receiving_note"]
    if line.get("is_acknowledged"):
        details["isAcknowledged"] = True
    if line.get("subscription_interval") not in (None, ""):
        details["subscriptionInterval"] = int(float(line["subscription_interval"]))
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
    line_tags = as_list(line.get("line_tags"))
    if line_tags:
        out["tags"] = {"tagList": line_tags}
    for key, field in (("requester", "requester"), ("selector", "selector")):
        if line.get(key):
            out[field] = str(line[key])
    for key, field in LINE_FLAGS:
        if line.get(key):
            out[field] = True
    for key, field in LINE_UUIDS:
        if line.get(key):
            out[field] = line[key]
    if line.get("claiming_interval") not in (None, ""):
        out["claimingInterval"] = int(float(line["claiming_interval"]))
    if line.get("donor"):
        out["donor"] = line["donor"]
    donors = [r.organization(c) for c in as_list(line.get("donor_organization_codes"))]
    if donors:
        out["donorOrganizationIds"] = donors
    if line.get("rush"):
        out["rush"] = True
    for key, field in (("renewal_note", "renewalNote"),
                       ("cancellation_restriction_note",
                        "cancellationRestrictionNote")):
        if line.get(key):
            out[field] = line[key]
    if line.get("receipt_date"):
        out["receiptDate"] = date_time(line["receipt_date"])
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
        if line.get("resource_url"):
            out["eresource"]["resourceUrl"] = line["resource_url"]
        if line.get("user_limit"):
            out["eresource"]["userLimit"] = str(line["user_limit"])
        if line.get("trial"):
            out["eresource"]["trial"] = True
    if physical:
        out["physical"] = {"createInventory": "None"}
        out["physical"]["materialType"] = r.material_type(line["material_type"])
        volumes = as_list(line.get("volumes"))
        if volumes:
            out["physical"]["volumes"] = volumes
        if line.get("material_supplier_code"):
            out["physical"]["materialSupplier"] = r.organization(
                line["material_supplier_code"])
        if line.get("expected_receipt_date"):
            out["physical"]["expectedReceiptDate"] = date_time(
                line["expected_receipt_date"])
    locations = location_list(line)
    if locations:
        out["locations"] = [{
            "locationId": r.location(loc["code"]),
            "quantityPhysical": loc["quantity_physical"],
            "quantityElectronic": loc["quantity_electronic"]}
            for loc in locations]
    return out


def date_time(value):
    """A YYYY-MM-DD date as the date-time FOLIO's schema wants."""
    value = str(value)
    return value if "T" in value else value + "T00:00:00.000+00:00"


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

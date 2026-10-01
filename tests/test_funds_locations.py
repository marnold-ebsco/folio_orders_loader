from folio_orders_loader.builder import build_order
from folio_orders_loader.lookups import Resolver
from folio_orders_loader.mapping import check_map, map_row
from folio_orders_loader.records import validate_line

from test_builder import FakeClient, line


def pol(**kw):
    order = build_order("P1", [line(**kw)], Resolver(FakeClient()))
    return order["compositePoLines"][0]


def test_single_fund_unchanged():
    fd = pol()["fundDistribution"]
    assert fd == [{"fundId": "fund-F", "code": "F",
                   "expenseClassId": "/finance/expense-classes:GEN",
                   "distributionType": "percentage", "value": 100.0}]


def test_several_funds_percentage_and_amount():
    fd = pol(fund_distribution=[
        {"code": "A", "expense_class_code": "GEN", "value": "60"},
        {"code": "B", "expense_class_code": "GEN", "value": 40}])["fundDistribution"]
    assert [(f["code"], f["value"], f["distributionType"]) for f in fd] == [
        ("A", 60.0, "percentage"), ("B", 40.0, "percentage")]
    fd = pol(fund_distribution=[
        {"code": "A", "value": 4, "type": "amount"},
        {"code": "B", "value": 6.5, "type": "amount"}])["fundDistribution"]
    assert fd[1]["distributionType"] == "amount"
    assert fd[0]["expenseClassId"] == "/finance/expense-classes:GEN"


def test_fund_problems():
    bad = line(fund_distribution=[{"code": "A", "value": 60},
                                  {"code": "B", "value": 30}])
    assert any("add to 90" in p for p in validate_line(bad))
    assert any("type 'x'" in p for p in validate_line(
        line(fund_distribution=[{"code": "A", "type": "x"}])))
    no_fund = line()
    del no_fund["fund_code"]
    assert any("missing fund_code" in p for p in validate_line(no_fund))


def test_quantity_and_cost_extras():
    p = pol(order_format="P/E Mix", material_type="journal",
            quantity_physical=3, quantity_electronic="2", discount="10",
            discount_type="percentage", additional_cost=4, exchange_rate="1.25")
    assert p["cost"] == {
        "currency": "USD", "listUnitPriceElectronic": 10.5, "quantityElectronic": 2,
        "listUnitPrice": 10.5, "quantityPhysical": 3, "discount": 10.0,
        "discountType": "percentage", "additionalCost": 4.0, "exchangeRate": 1.25}


def test_default_location_follows_line_quantity():
    p = pol(order_format="Physical Resource", material_type="journal",
            quantity_physical=3, location_code="L")
    assert p["locations"] == [{"locationId": "/locations:L", "quantityPhysical": 3,
                               "quantityElectronic": 0}]


def test_several_locations_must_match_quantity():
    kw = dict(order_format="Physical Resource", material_type="journal",
              quantity_physical=3)
    ok = pol(locations=[{"code": "L1", "quantity_physical": 2},
                        {"code": "L2", "quantity_physical": 1}], **kw)
    assert [x["quantityPhysical"] for x in ok["locations"]] == [2, 1]
    bad = line(locations=[{"code": "L1", "quantity_physical": 2}], **kw)
    assert any("add to 2" in p for p in validate_line(bad))
    both = line(locations=[{"code": "L1"}], location_code="L", **kw)
    assert any("not both" in p for p in validate_line(both))


def test_discount_type_needs_discount_and_valid_value():
    assert any("without discount" in p for p in validate_line(
        line(discount_type="amount")))
    assert any("discount_type" in p for p in validate_line(
        line(discount="1", discount_type="pct")))
    assert any("whole number" in p for p in validate_line(
        line(quantity_electronic="1.5")))


def spec(name, column=None, **kw):
    return {"folio_field": name, "legacy_field": column or "Not mapped", **kw}


def test_mapping_repeating_groups():
    mapping = {"data": [
        spec("fund_distribution[0].code", "F1"),
        spec("fund_distribution[0].value", "P1"),
        spec("fund_distribution[1].code", "F2"),
        spec("fund_distribution[1].value", "P2"),
        spec("locations[0].code", "L"),
        spec("locations[0].quantity_physical", "Q"),
        spec("discount", "D")]}
    row = {"F1": "A", "P1": "$1,000.50", "F2": "B", "P2": "40", "L": "X",
           "Q": "2", "D": "$5"}
    got, errors = map_row(mapping, row)
    assert errors == []
    assert got["fund_distribution"] == [{"code": "A", "value": "1000.50"},
                                        {"code": "B", "value": "40"}]
    assert got["locations"] == [{"code": "X", "quantity_physical": "2"}]
    assert got["discount"] == "5"


def test_check_map_fund_requirement():
    base = [spec(n, "c") for n in (
        "po_number", "vendor_code", "title", "order_format", "cost", "currency",
        "order_type", "acquisition_method")]
    assert any("fund_code" in p for p in check_map({"data": base}))
    assert check_map({"data": base + [spec("fund_distribution[0].code", "c")]}) == []
    assert check_map({"data": base + [spec("fund_code", "c"),
                                      spec("expense_class_code", "c")]}) == []
    assert any("unknown" in p for p in check_map(
        {"data": base + [spec("locations[0].bogus", "c")]}))

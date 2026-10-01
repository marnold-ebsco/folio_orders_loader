from folio_orders_loader.builder import build_order
from folio_orders_loader.lookups import Resolver
from folio_orders_loader.records import validate_line

from test_builder import FakeClient, line
from test_funds_locations import pol


def test_inventory_and_checkin():
    p = pol(order_format="P/E Mix", material_type="journal",
            create_inventory_physical="Instance, Holding, Item",
            create_inventory_electronic="Instance", checkin_items=True)
    assert p["physical"]["createInventory"] == "Instance, Holding, Item"
    assert p["eresource"]["createInventory"] == "Instance"
    assert p["checkinItems"] is True


def test_defaults():
    p = pol()
    assert p["checkinItems"] is False
    assert p["eresource"]["createInventory"] == "None"


def test_electronic_rejects_item():
    msgs = validate_line({"create_inventory_electronic": "Instance, Holding, Item"})
    assert any("create_inventory_electronic" in m for m in msgs)


def test_acq_units():
    order = build_order("P1", [line(acq_unit_names="A|B")], Resolver(FakeClient()))
    assert order["acqUnitIds"] == ["/acquisitions-units/units:A",
                                   "/acquisitions-units/units:B"]
    assert "acqUnitIds" not in build_order("P1", [line()], Resolver(FakeClient()))

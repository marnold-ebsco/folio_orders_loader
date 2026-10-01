from folio_orders_loader.records import validate_line

from test_funds_locations import pol

U = "11111111-1111-4111-8111-111111111111"


def test_built():
    p = pol(automatic_export=True, collection=True, claiming_interval="30",
            donor="Ann", instance_id=U, is_package=True)
    assert p["automaticExport"] and p["collection"] and p["isPackage"]
    assert p["claimingInterval"] == 30 and p["donor"] == "Ann"
    assert p["instanceId"] == U


def test_absent_by_default():
    assert not {"automaticExport", "instanceId", "donor", "claimingInterval"} & set(pol())


def test_validation():
    msgs = validate_line({"agreement_id": "x", "claiming_interval": "a"})
    assert any("agreement_id" in m for m in msgs)
    assert any("claiming_interval" in m for m in msgs)

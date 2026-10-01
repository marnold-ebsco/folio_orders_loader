import pytest

from folio_orders_loader.records import validate_line

from test_builder import line


def bad(**kw):
    return [m for m in validate_line(line(**kw)) if "not allowed" in m]


@pytest.mark.parametrize("key,value", [
    ("volumes", "v.1"), ("material_supplier_code", "X"),
    ("expected_receipt_date", "2026-01-01"), ("receipt_due", "2026-01-01"),
    ("create_inventory_physical", "Instance")])
def test_physical_key_on_electronic_line(key, value):
    assert bad(**{key: value})


@pytest.mark.parametrize("key,value", [
    ("resource_url", "http://x"), ("user_limit", 5), ("trial", True),
    ("expected_activation", "2026-01-01"), ("activation_due", 3),
    ("create_inventory_electronic", "Instance")])
def test_electronic_key_on_physical_line(key, value):
    assert bad(order_format="Physical Resource", material_type="journal",
               **{key: value})


def test_mix_allows_both_and_empty_values_pass():
    assert not bad(order_format="P/E Mix", material_type="journal",
                   resource_url="http://x", volumes="v.1")
    assert not bad(volumes="", trial=False)


def test_material_type_and_access_provider_not_rejected():
    assert not bad(material_type="journal", access_provider_code="X")
    assert not bad(order_format="Physical Resource", material_type="journal",
                   access_provider_code="X")

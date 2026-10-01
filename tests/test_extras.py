from folio_orders_loader.mapping import map_row
from folio_orders_loader.records import validate_line

from test_funds_locations import pol


def test_electronic_extras():
    p = pol(resource_url="https://x.org", user_limit=5, trial=True)
    assert p["eresource"]["resourceUrl"] == "https://x.org"
    assert p["eresource"]["userLimit"] == "5" and p["eresource"]["trial"] is True


def test_details_and_notes():
    p = pol(receiving_note="hi", is_acknowledged=True, subscription_interval=30,
            renewal_note="r", cancellation_restriction_note="c",
            receipt_date="2026-01-02",
            product_ids=[{"type": "ISSN", "value": "1", "qualifier": "q"}])
    assert p["details"]["receivingNote"] == "hi"
    assert p["details"]["isAcknowledged"] is True
    assert p["details"]["subscriptionInterval"] == 30
    assert p["details"]["productIds"][0]["qualifier"] == "q"
    assert p["renewalNote"] == "r" and p["cancellationRestrictionNote"] == "c"
    assert p["receiptDate"] == "2026-01-02T00:00:00.000+00:00"


def test_absent_by_default():
    p = pol()
    assert not {"renewalNote", "receiptDate"} & set(p)
    assert "resourceUrl" not in p.get("eresource", {})


def test_bad_interval():
    assert any("subscription_interval" in m
               for m in validate_line({"subscription_interval": "x"}))


def test_mapping_dates():
    mapping = {"data": [{"folio_field": "receipt_date", "legacy_field": "D",
                         "date_format": "%m/%d/%Y"},
                        {"folio_field": "trial", "legacy_field": "T"}]}
    out, errs = map_row(mapping, {"D": "03/04/2026", "T": "y"})
    assert errs == [] and out == {"receipt_date": "2026-03-04", "trial": True}

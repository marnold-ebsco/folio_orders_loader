from folio_orders_loader.mapping import check_map, map_row
from folio_orders_loader.records import validate_line

from test_funds_locations import line, pol


def test_bibliographic_fields_built():
    p = pol(edition="2nd", publication_date="2024",
            contributors=[{"name": "Smith, J.", "type": "Personal name"},
                          {"name": "ACME", "type": "Corporate name"}])
    assert p["edition"] == "2nd"
    assert p["publicationDate"] == "2024"
    assert p["contributors"] == [
        {"contributor": "Smith, J.",
         "contributorNameTypeId": "/contributor-name-types:Personal name"},
        {"contributor": "ACME",
         "contributorNameTypeId": "/contributor-name-types:Corporate name"}]


def test_absent_by_default():
    p = pol()
    assert not {"edition", "publicationDate", "contributors"} & set(p)


def test_contributor_problems():
    probs = validate_line(line(contributors=[{"name": "X"}, {"type": "T"}]))
    assert "contributors[0]: missing type" in probs
    assert "contributors[1]: missing name" in probs


def test_mapping():
    mapping = {"data": [
        {"folio_field": "contributors[0].name", "legacy_field": "Author"},
        {"folio_field": "contributors[0].type", "value": "Personal name"},
        {"folio_field": "edition", "legacy_field": "Ed"},
        {"folio_field": "publication_date", "legacy_field": "Year"}]}
    assert not [p for p in check_map(mapping) if "unknown" in p or "unexpected" in p]
    out, errs = map_row(mapping, {"Author": "Doe", "Ed": "3", "Year": "1999"})
    assert errs == []
    assert out == {"contributors": [{"name": "Doe", "type": "Personal name"}],
                   "edition": "3", "publication_date": "1999"}

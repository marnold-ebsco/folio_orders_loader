from folio_orders_loader.mapping import map_row

from test_funds_locations import pol


def test_built():
    p = pol(line_tags="a| b", requester="Jo", selector="Al", rush=True)
    assert p["tags"] == {"tagList": ["a", "b"]}
    assert (p["requester"], p["selector"], p["rush"]) == ("Jo", "Al", True)


def test_absent_by_default():
    assert not {"tags", "requester", "selector", "rush"} & set(pol())


def test_rush_false_omitted_and_mapping():
    assert "rush" not in pol(rush=False)
    mapping = {"data": [{"folio_field": "rush", "legacy_field": "R"},
                        {"folio_field": "line_tags", "legacy_field": "T"}]}
    out, errs = map_row(mapping, {"R": "yes", "T": "x|y"})
    assert errs == [] and out == {"rush": True, "line_tags": "x|y"}

from folio_orders_loader import mapping as m


def spec(name, col=None, **kw):
    return {"folio_field": name, "legacy_field": col or m.NOT_MAPPED, **kw}


def test_template_fails_check_until_required_mapped():
    problems = m.check_map(m.template())
    assert any("'po_number' is not mapped" in p for p in problems)


def test_check_map_flags_unknown_duplicate_and_extra_keys():
    mp = {"data": [spec("bogus", "A"), spec("title", "T"),
                   spec("title", "T2", junk=1)]}
    text = " ".join(m.check_map(mp))
    assert "unknown folio_field 'bogus'" in text
    assert "duplicate folio_field 'title'" in text
    assert "unexpected key 'junk'" in text


def test_precedence_literal_fallback_and_translate():
    mp = {"data": [
        spec("vendor_code", "Vendor", translate={"Acme Books": "ACME"}),
        spec("currency", "Cur", fallback_value="USD"),
        spec("fund_code", "Fund", fallback_legacy_field="Fund2"),
        spec("order_format", "Fmt", translate={"Print": "Physical Resource"})]}
    row = {"Vendor": " acme books ", "Cur": "", "Fund": "", "Fund2": "F1",
           "Fmt": "Mystery"}
    line, warns = m.map_row(mp, row)
    assert line == {"vendor_code": "ACME", "currency": "USD",
                    "fund_code": "F1", "order_format": "Mystery"}
    assert warns == ["order_format: no translation for 'Mystery'"]  # now an error


def test_coercion_and_product_ids():
    mp = {"data": [
        spec("cost", "Price"), spec("is_subscription", "Sub"),
        spec("product_ids[0].type", value="ISSN"),
        spec("product_ids[0].value", "ISSN")]}
    line, _ = m.map_row(mp, {"Price": "$1,234.50", "Sub": "Yes",
                             "ISSN": "1234-5678"})
    assert line["cost"] == "1234.50"
    assert line["is_subscription"] is True
    assert line["product_ids"] == [{"type": "ISSN", "value": "1234-5678"}]


def test_map_file_reads_bom_tsv_and_numbers_rows(tmp_path):
    f = tmp_path / "in.tsv"
    f.write_text("﻿PO\tTitle\nP1\tA\nP2\t\n", encoding="utf-8")
    mp = {"data": [spec("po_number", "PO"), spec("title", "Title")]}
    lines, warns = m.map_file(mp, f)
    assert lines == [{"po_number": "P1", "title": "A"}, {"po_number": "P2"}]
    assert warns == []


def test_date_format_and_bad_date():
    mp = {"data": [spec("subscription_to", "To", date_format="%m/%d/%Y")]}
    line, errs = m.map_row(mp, {"To": "12/31/2026"})
    assert line["subscription_to"] == "2026-12-31" and errs == []
    _, errs = m.map_row(mp, {"To": "soon"})
    assert len(errs) == 1 and "not a date" in errs[0]


def test_rules_split_combine_strip():
    mp = {"data": [
        spec("title", "T", rules=[{"op": "split", "sep": "|", "index": 1}]),
        spec("publisher", rules=[{"op": "combine", "fields": ["A", "B"],
                                  "sep": " "}]),
        spec("fund_code", "F", rules=[{"op": "strip_prefix", "text": "X-"},
                                      {"op": "upper"}])]}
    line, errs = m.map_row(mp, {"T": "a|b", "A": "Acme", "B": "Press",
                                "F": "X-abc"})
    assert line == {"title": "b", "publisher": "Acme Press", "fund_code": "ABC"}
    assert errs == []


def test_check_map_flags_bad_rule_and_date_format():
    mp = {"data": [spec("title", "T", rules=[{"op": "nope"}]),
                   spec("cost", "C", date_format="%Y")]}
    text = " ".join(m.check_map(mp))
    assert "bad rule" in text and "non-date field" in text


def test_quoted_delimiter_in_cell(tmp_path):
    f = tmp_path / "q.tsv"
    f.write_text('PO\tTitle\nP1\t"a\tb ""c"""\n', encoding="utf-8")
    mp = {"data": [spec("po_number", "PO"), spec("title", "Title")]}
    lines, _ = m.map_file(mp, f)
    assert lines == [{"po_number": "P1", "title": 'a\tb "c"'}]

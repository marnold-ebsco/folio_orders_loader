import json

from folio_orders_loader import cli, tools


def test_template_writes_map(tmp_path, capsys):
    out = tmp_path / "map.json"
    assert cli.main(["template", "--out", str(out)]) == 0
    got = json.loads(out.read_text())
    assert got["data"]
    assert "reader" not in got


def test_template_with_reader(tmp_path):
    out = tmp_path / "map.json"
    assert cli.main(["template", "--out", str(out), "--with-reader"]) == 0
    assert json.loads(out.read_text())["reader"]["delimiter"] == "	"


def test_validate_reports_map_problems(tmp_path, capsys):
    mp = tmp_path / "map.json"
    cli.main(["template", "--out", str(mp)])
    data = tmp_path / "d.tsv"
    data.write_text("A\n1\n")
    try:
        cli.main(["validate", str(data), "--mapping", str(mp)])
    except SystemExit as exc:
        assert exc.code == 2
    assert "is not mapped" in capsys.readouterr().out


def test_validate_without_ini_flags_bad_po(tmp_path, capsys):
    rows = {"po_number": "PO-1", "vendor_code": "V", "title": "T",
            "order_format": "Electronic Resource", "cost": "5",
            "currency": "USD", "fund_code": "F", "expense_class_code": "E",
            "order_type": "One-Time", "acquisition_method": "Purchase"}
    mp = {"reader": {"delimiter": ","},
          "data": [{"folio_field": k, "legacy_field": k} for k in rows]}
    mpath = tmp_path / "map.json"
    mpath.write_text(json.dumps(mp))
    data = tmp_path / "d.csv"
    data.write_text(",".join(rows) + "\n" + ",".join(rows.values()) + "\n")
    assert cli.main(["validate", str(data), "--mapping", str(mpath)]) == 1
    assert "must be 1-22 letters/digits" in capsys.readouterr().out


def test_read_targets_rejects_bad_type(tmp_path):
    f = tmp_path / "t.csv"
    f.write_text("type,number,note\nXX,A1,\n")
    try:
        tools.read_targets(str(f))
    except ValueError as exc:
        assert "row 2" in str(exc)
    else:
        raise AssertionError("expected ValueError")

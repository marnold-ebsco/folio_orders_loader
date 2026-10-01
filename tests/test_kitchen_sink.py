"""Run the kitchen-sink fixture through map -> validate -> load (fake client)."""
import json

import kitchen_sink_data as ks
from folio_orders_loader import mapping
from folio_orders_loader.loader import load
from folio_orders_loader.records import group_by_po

from test_builder import FakeClient

TSV = ks.FIXTURES / "kitchen_sink.tsv"
MAP = ks.FIXTURES / "kitchen_sink_map.json"


class SinkClient(FakeClient):
    """FakeClient that also knows tenant addresses, a missing vendor, and a
    FOLIO that rejects one PO."""

    def folio_get(self, path, key=None, query_params=None):
        if path == "/settings/entries":
            return [{"id": "addr-main", "value": {"name": "Main Library"}}]
        if (path == "/organizations/organizations"
                and "NOSUCHVENDOR" in query_params["query"]):
            return []
        return super().folio_get(path, key, query_params)

    def folio_post(self, path, body):
        if body["poNumber"] in ks.REJECTED:
            raise RuntimeError(
                '422 {"errors":[{"message":"Expense class not found",'
                '"code":"budgetExpenseClassNotFound"}]}')
        return super().folio_post(path, body)


def mapped():
    mp = mapping.load_map(MAP)
    assert mapping.check_map(mp) == []
    return mapping.map_file(mp, TSV)


def test_committed_fixture_matches_generator(tmp_path):
    ks.write_tsv(tmp_path / "a.tsv")
    ks.write_map(tmp_path / "a.json")
    assert (tmp_path / "a.tsv").read_bytes() == TSV.read_bytes()
    assert json.loads((tmp_path / "a.json").read_text()) == json.loads(MAP.read_text())


def test_every_expected_status_is_one_po_per_case():
    assert len(ks.EXPECTED) == len(ks.CASES)


def test_mapping_errors_hit_only_the_map_error_pos():
    lines, errors = mapped()
    assert errors, "the fixture must produce mapping errors"
    rows_with_errors = {int(e.split(":")[0].split()[1]) for e in errors}
    bad_pos = {lines[n - 2]["po_number"] for n in rows_with_errors}
    assert bad_pos == ks.MAP_ERROR_POS


def test_validation_flags_exactly_the_invalid_pos():
    lines, _ = mapped()
    _, problems = group_by_po(lines)
    invalid = {po for po, status in ks.EXPECTED.items() if status == "invalid"}
    # an untranslated format value also fails validation; that is a map-error PO
    assert invalid <= set(problems) <= invalid | ks.MAP_ERROR_POS, {
        po: problems.get(po) for po in set(problems) ^ invalid}


def test_load_outcome_per_po():
    lines, _ = mapped()
    client = SinkClient(existing=ks.EXISTING)
    results = {po: (status, detail) for po, status, detail in
               load(client, lines, live=True)}
    for po, want in ks.EXPECTED.items():
        if want == "map-error":  # the CLI refuses to load these; the loader
            continue             # itself only sees whatever the mapper produced
        assert results[po][0] == want, (po, results[po])
    assert "budgetExpenseClassNotFound" in results["KS501"][1]
    assert results["KS003"][1].count(",") == 1  # two lines created
    # a rejected PO does not stop the rest of the run
    created = [o["poNumber"] for o in client.posted]
    assert "KS001" in created and "KS008" in created
    assert "KS101" not in created and "KS301" not in created


def test_dry_run_posts_nothing():
    lines, _ = mapped()
    client = SinkClient(existing=ks.EXISTING)
    results = load(client, lines, live=False)
    assert client.posted == []
    assert {r[1] for r in results} <= {"dry-run", "invalid", "exists", "lookup-failed"}


def test_rerun_skips_everything_already_created():
    lines, _ = mapped()
    first = SinkClient(existing=ks.EXISTING)
    load(first, lines, live=True)
    created = {o["poNumber"] for o in first.posted}
    second = SinkClient(existing=ks.EXISTING | created)
    again = {po: s for po, s, _ in load(second, lines, live=True)}
    assert all(again[po] == "exists" for po in created)
    assert second.posted == []


def test_built_orders_carry_the_mapped_values():
    lines, _ = mapped()
    client = SinkClient(existing=ks.EXISTING)
    load(client, lines, live=True)
    orders = {o["poNumber"]: o for o in client.posted}
    three = orders["KS003"]["compositePoLines"]
    assert [ln["cost"]["listUnitPrice"] for ln in three] == [1234.5, 2000.0]
    four = orders["KS004"]["compositePoLines"][0]
    assert [d["value"] for d in four["fundDistribution"]] == [60.0, 40.0]
    assert len(four["locations"]) == 2 and len(four["contributors"]) == 2
    assert orders["KS005"]["compositePoLines"][0]["fundDistribution"][0]["code"] == "TEST-ELEC"
    six = orders["KS006"]
    assert six["notes"] == ["first note", "second note"]
    assert six["billTo"] == "addr-main" and six["poNumberPrefix"] == "KS"
    assert orders["KS007"]["compositePoLines"][0]["rush"] is True

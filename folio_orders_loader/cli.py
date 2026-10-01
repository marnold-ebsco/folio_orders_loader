"""Command line: python -m folio_orders_loader load|validate|template|delete|export."""
import argparse
import csv
import json
import sys
from pathlib import Path

from . import mapping, tools
from .budgets import check_budgets
from .builder import build_order
from .client import connect
from .loader import load, po_exists
from .lookups import LookupError_, Resolver
from .records import group_by_po


def _add_input(p):
    p.add_argument("file", help="delimited data file")
    p.add_argument("--mapping", required=True, help="mapping JSON (see 'template')")
    p.add_argument("--delimiter", help="override the map's reader delimiter "
                   "(use \\t for tab)")
    p.add_argument("--encoding", help="override the map's reader encoding")


def build_parser():
    p = argparse.ArgumentParser(prog="folio_orders_loader", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("load", help="create Pending POs (dry run unless --live)")
    _add_input(s)
    s.add_argument("--ini", required=True)
    s.add_argument("--live", action="store_true", help="actually POST (default: dry run)")
    s.add_argument("--open", action="store_true", dest="open_orders",
                   help="with --live, open each PO after creating it (needs budget)")
    s.add_argument("--log", help="write a CSV result log here")

    s = sub.add_parser("validate", help="check map, data and tenant codes; no POST")
    _add_input(s)
    s.add_argument("--ini", help="tenant .ini; without it the code lookups are skipped")

    s = sub.add_parser("template", help="write a blank mapping file")
    s.add_argument("--out", help="output file (default: stdout)")

    s = sub.add_parser("delete", help="delete Pending POs/lines listed in a CSV")
    s.add_argument("csv")
    s.add_argument("--ini", required=True)
    s.add_argument("--live", action="store_true", help="actually delete")
    s.add_argument("--max", type=int, default=50, help="refuse longer lists")
    s.add_argument("--backup-dir", default="out/deleted_backup")
    s.add_argument("--log", default="out/delete_log.csv")

    s = sub.add_parser("export", help="save POs as JSON")
    s.add_argument("po_numbers", nargs="+")
    s.add_argument("--ini", required=True)
    s.add_argument("--out", help="output file (default: stdout)")
    return p


def _reader_overrides(mp, args):
    reader = dict(mp.get("reader") or {})
    if args.delimiter:
        reader["delimiter"] = args.delimiter.encode().decode("unicode_escape")
    if args.encoding:
        reader["encoding"] = args.encoding
    mp["reader"] = reader


def _mapped_lines(args):
    """Return (lines, errors) or raise SystemExit when the map is unusable."""
    mp = mapping.load_map(args.mapping)
    bad = mapping.check_map(mp)
    if bad:
        print("mapping problems:")
        for b in bad:
            print("  " + b)
        raise SystemExit(2)
    _reader_overrides(mp, args)
    return mapping.map_file(mp, args.file)


def _write_csv(path, header, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def cmd_template(args):
    text = json.dumps(mapping.template(), indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print("wrote", args.out)
    else:
        print(text)
    return 0


def cmd_validate(args):
    lines, map_errors = _mapped_lines(args)
    pos, problems = group_by_po(lines)
    errors = len(map_errors)
    for e in map_errors:
        print("error:", e)
    for po, msgs in problems.items():
        errors += len(msgs)
        for m in msgs:
            print("error: PO %s: %s" % (po, m))
    if args.ini:
        client = connect(args.ini)
        resolver = Resolver(client)
        for po, group in pos.items():
            if po in problems:
                continue
            if po_exists(client, po):
                print("note: PO %s already exists and would be skipped" % po)
                continue
            try:
                build_order(po, group, resolver)
            except (LookupError_, ValueError) as exc:
                errors += 1
                print("error: PO %s: %s" % (po, exc))
                continue
            for msg in check_budgets(group, resolver):
                errors += 1
                print("error: PO %s: %s" % (po, msg))
    else:
        print("note: no --ini, code lookups skipped")
    print("%d line(s), %d PO(s), %d error(s)" % (len(lines), len(pos), errors))
    return 1 if errors else 0


def cmd_load(args):
    lines, map_errors = _mapped_lines(args)
    if map_errors:
        for e in map_errors:
            print("error:", e)
        print("not loading: fix the mapping errors above (run 'validate')")
        return 1
    client = connect(args.ini)
    print("%d line(s); %s" % (len(lines), "LIVE - POSTING" if args.live else "dry run"))
    results = load(client, lines, live=args.live, open_orders=args.open_orders)
    for po, status, detail in results:
        print("%-22s %-13s %s" % (po, status, detail))
    if args.log:
        _write_csv(args.log, ["po_number", "status", "detail"], results)
    bad = {"invalid", "lookup-failed", "error", "open-error"}
    return 1 if any(r[1] in bad for r in results) else 0


def cmd_delete(args):
    targets = tools.read_targets(args.csv)
    if not targets:
        print("nothing listed in", args.csv)
        return 0
    if len(targets) > args.max:
        raise SystemExit("%d entries is more than --max %d; raise --max if intended"
                         % (len(targets), args.max))
    client = connect(args.ini)
    print("%d entries; %s" % (len(targets), "LIVE - DELETING" if args.live else "dry run"))
    results = tools.delete(client, targets, args.live, args.backup_dir)
    _write_csv(args.log, ["type", "number", "status", "detail", "note"], results)
    for kind, number, status, detail, _ in results:
        print("%-3s %-22s %-10s %s" % (kind, number, status, detail))
    return 1 if any(r[2] == "error" for r in results) else 0


def cmd_export(args):
    orders = tools.export_orders(connect(args.ini), args.po_numbers)
    text = json.dumps(orders, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote %d of %d order(s) to %s"
              % (len(orders), len(args.po_numbers), args.out))
    else:
        print(text)
    return 0


COMMANDS = {"load": cmd_load, "validate": cmd_validate, "template": cmd_template,
            "delete": cmd_delete, "export": cmd_export}


def main(argv=None):
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

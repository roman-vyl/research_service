#!/usr/bin/env python3
"""Check an Experiment ``materialize`` block against the runs it already has.

``research-run-calculation-v1`` task 2.1. Read-only: it never writes the result
table, the manifest or any run. Standard library only, so it runs with a bare
``python3`` next to the data.

Two commands:

``suggest``  reads ``request.json`` of every row with a live run and prints the
             raw_spec leaves that vary between runs, the table columns that equal
             each of them on every row, the constant part of the strategy and the
             Research policy. A starting point for writing the block by hand.

``check``    materializes every row with a live run from the block (deep copy of
             the template, each binding copies the row cell to its JSON Pointer),
             asks Strategy Engine ``/v1/strategies/{id}/validate`` for the
             ``config_hash`` of the materialized spec and of the spec in the run's
             ``request.json``, and compares them, together with the identity
             fields and the Research policy. Exit code 1 on any mismatch.

A row has a live run when its ``run_id`` cell is not empty and
``<runs-root>/<run_id>/request.json`` exists.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

csv.field_size_limit(sys.maxsize)


# --- inputs -------------------------------------------------------------------


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(table: Path) -> tuple[list[str], list[list[str]]]:
    with table.open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        return header, list(reader)


def _live_rows(
    header: list[str], rows: list[list[str]], run_id_column: str, runs_root: Path
) -> tuple[list[tuple[int, dict[str, str], Path]], int, int]:
    pos = header.index(run_id_column)
    live: list[tuple[int, dict[str, str], Path]] = []
    empty = dangling = 0
    for index, row in enumerate(rows):
        run_id = row[pos] if len(row) > pos else ""
        if not run_id:
            empty += 1
            continue
        request = runs_root / run_id / "request.json"
        if not request.is_file():
            dangling += 1
            continue
        live.append((index, dict(zip(header, row)), request))
    return live, empty, dangling


# --- materialize (same rules as the service) ----------------------------------------


def _parts(path: str) -> list[str]:
    if not path.startswith("/"):
        raise ValueError(f"not a JSON Pointer: {path!r}")
    return [p.replace("~1", "/").replace("~0", "~") for p in path[1:].split("/")]


def _step(node: Any, part: str, path: str) -> tuple[Any, Any]:
    if isinstance(node, dict) and part in node:
        return node, part
    if isinstance(node, list) and part.isdigit() and int(part) < len(node):
        return node, int(part)
    raise ValueError(f"path {path} does not exist in the template")


def _set(document: Any, path: str, value: Any) -> None:
    parts = _parts(path)
    node = document
    for part in parts[:-1]:
        container, key = _step(node, part, path)
        node = container[key]
    container, key = _step(node, parts[-1], path)
    container[key] = value


def _parse(text: str, kind: str) -> Any:
    if text == "":
        raise ValueError("empty cell")
    if kind == "string":
        return text
    number = Decimal(text)
    if not number.is_finite():
        raise ValueError(f"{text!r} is not finite")
    if kind == "integer":
        if number != number.to_integral_value():
            raise ValueError(f"{text!r} is not an integer")
        return int(number)
    return float(number)


def _materialize(block: dict[str, Any], cells: dict[str, str]) -> dict[str, Any]:
    spec = copy.deepcopy(block["strategy_template"])
    for binding in block["bindings"]:
        _set(spec, binding["path"], _parse(cells.get(binding["column"], ""), binding["type"]))
    return spec


# --- Engine -----------------------------------------------------------------------


class Engine:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._cache: dict[str, tuple[str | None, str | None]] = {}
        self.calls = 0

    def config_hash(self, strategy_id: str, raw_spec: dict[str, Any]) -> tuple[str | None, str | None]:
        key = strategy_id + "\0" + json.dumps(raw_spec, sort_keys=True, separators=(",", ":"))
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        body = json.dumps({"strategy_id": strategy_id, "raw_spec": raw_spec}).encode()
        request = urllib.request.Request(
            f"{self._base}/v1/strategies/{strategy_id}/validate",
            data=body,
            headers={"content-type": "application/json"},
            method="POST",
        )
        self.calls += 1
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                result = (json.loads(response.read())["config_hash"], None)
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500:
                result = (None, exc.read().decode("utf-8", "replace")[:500])
            else:
                raise
        self._cache[key] = result
        return result


# --- comparison --------------------------------------------------------------------


def _leaves(node: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            out.update(_leaves(value, f"{prefix}/{str(key).replace('~', '~0').replace('/', '~1')}"))
        return out
    if isinstance(node, list):
        out = {}
        for i, value in enumerate(node):
            out.update(_leaves(value, f"{prefix}/{i}"))
        return out if node else {prefix: []}
    return {prefix: node}


def _diff(a: Any, b: Any) -> list[dict[str, Any]]:
    la, lb = _leaves(a), _leaves(b)
    out = []
    for path in sorted(set(la) | set(lb)):
        if la.get(path, "<absent>") != lb.get(path, "<absent>"):
            out.append({"path": path, "materialized": la.get(path, "<absent>"), "request": lb.get(path, "<absent>")})
    return out


def _same_value(a: Any, b: Any) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_same_value(a[k], b[k]) for k in a)
    if a is None or b is None:
        return a is b
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except InvalidOperation:
        return a == b


def _policy_diffs(policy: dict[str, Any], request: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for key in ("range_policy", "range", "execution", "accounting", "managed_policy_enabled"):
        expected = policy.get(key)
        actual = request.get(key)
        if key in ("execution", "accounting") and isinstance(expected, dict) and isinstance(actual, dict):
            # The policy may leave defaults out; compare the keys it states and that the request states.
            keys = set(expected) | set(actual)
            mismatched = [k for k in sorted(keys) if not _same_value(expected.get(k), actual.get(k))]
            if mismatched:
                out.append({"field": key, "keys": mismatched, "policy": expected, "request": actual})
        elif not _same_value(expected, actual):
            out.append({"field": key, "policy": expected, "request": actual})
    return out


# --- commands ----------------------------------------------------------------------


def _experiment(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    manifest = _load(args.manifest)
    return manifest, args.manifest.parent / manifest["result_schema"]["table"]


def cmd_suggest(args: argparse.Namespace) -> int:
    manifest, table = _experiment(args)
    schema = manifest["result_schema"]
    header, rows = _rows(table)
    live, empty, dangling = _live_rows(header, rows, schema["run_id_column"], args.runs_root)
    if not live:
        print(json.dumps({"rows": len(rows), "live_runs": 0, "empty_run_id": empty, "dangling": dangling}))
        return 1
    requests = [(cells, _load(path)) for _, cells, path in live]
    leaves = [_leaves(r["strategy"]["raw_spec"]) for _, r in requests]
    all_paths = sorted(set().union(*leaves))
    varying = [p for p in all_paths if len({json.dumps(lv.get(p, "<absent>")) for lv in leaves}) > 1]
    suggestions = {}
    for path in varying:
        columns = []
        for column in header:
            ok = True
            for (cells, _), lv in zip(requests, leaves):
                if not _same_value(lv.get(path), cells.get(column, "")):
                    ok = False
                    break
            if ok:
                columns.append(column)
        values = sorted({json.dumps(lv.get(path, "<absent>")) for lv in leaves})
        suggestions["/raw_spec" + path] = {"columns": columns, "distinct_values": len(values), "sample": values[:8]}
    first = requests[0][1]
    policy_variants = {
        json.dumps({k: r.get(k) for k in ("range_policy", "range", "execution", "accounting", "managed_policy_enabled")},
                   sort_keys=True)
        for _, r in requests
    }
    identity_variants = {
        json.dumps({k: r["strategy"].get(k) for k in ("strategy_id", "ticker", "base_timeframe")}, sort_keys=True)
        for _, r in requests
    }
    print(
        json.dumps(
            {
                "rows": len(rows),
                "live_runs": len(live),
                "empty_run_id": empty,
                "dangling_run_id": dangling,
                "varying_paths": suggestions,
                "identity_variants": [json.loads(v) for v in sorted(identity_variants)],
                "policy_variants": [json.loads(v) for v in sorted(policy_variants)],
                "example_request": first,
            },
            indent=2,
            default=str,
        )
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    manifest, table = _experiment(args)
    schema = manifest["result_schema"]
    block = _load(args.materialize) if args.materialize else manifest.get("materialize")
    if not block:
        print("no materialize block", file=sys.stderr)
        return 2
    header, rows = _rows(table)
    missing = sorted(
        ({b["column"] for b in block["bindings"]} | set(block["result_bindings"])) - set(header)
    )
    unbound = sorted(m["column"] for m in schema["metrics"] if m["column"] not in block["result_bindings"])
    if missing or unbound:
        print(json.dumps({"missing_columns": missing, "unbound_metrics": unbound}, indent=2))
        return 1
    live, empty, dangling = _live_rows(header, rows, schema["run_id_column"], args.runs_root)
    engine = Engine(args.engine_url)
    template = block["strategy_template"]
    mismatches: list[dict[str, Any]] = []
    checked = 0
    for index, cells, request_path in live:
        request = _load(request_path)
        strategy = request["strategy"]
        problem: dict[str, Any] = {}
        try:
            spec = _materialize(block, cells)
        except ValueError as exc:
            problem["materialize_error"] = str(exc)
        else:
            identity = [
                k for k in ("strategy_id", "ticker", "base_timeframe") if spec.get(k) != strategy.get(k)
            ]
            if identity:
                problem["identity"] = {k: {"materialized": spec.get(k), "request": strategy.get(k)} for k in identity}
            got, err = engine.config_hash(spec["strategy_id"], spec["raw_spec"])
            want, err_r = engine.config_hash(strategy["strategy_id"], strategy["raw_spec"])
            if err or err_r or got != want:
                problem["config_hash"] = {"materialized": got, "request": want}
                if err:
                    problem["engine_error_materialized"] = err
                if err_r:
                    problem["engine_error_request"] = err_r
                problem["raw_spec_diff"] = _diff(spec["raw_spec"], strategy["raw_spec"])[:20]
            policy = _policy_diffs(block["research_policy"], request)
            if policy:
                problem["research_policy"] = policy
        checked += 1
        if problem:
            mismatches.append({"row_index": index, "run_id": request_path.parent.name, **problem})
            if len(mismatches) >= args.max_mismatches:
                break
    report = {
        "rows": len(rows),
        "live_runs": len(live),
        "empty_run_id": empty,
        "dangling_run_id": dangling,
        "checked": checked,
        "mismatches": len(mismatches),
        "engine_validate_calls": engine.calls,
        "template_strategy_id": template.get("strategy_id"),
        "first_mismatches": mismatches,
    }
    text = json.dumps(report, indent=2, default=str)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if mismatches else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("suggest", "check"):
        p = sub.add_parser(name)
        p.add_argument("--manifest", type=Path, required=True, help="Experiment manifest.json")
        p.add_argument("--runs-root", type=Path, required=True, help="folder holding <run_id>/ run bundles")
        if name == "check":
            p.add_argument("--materialize", type=Path, help="materialize block JSON (default: the manifest's own)")
            p.add_argument("--engine-url", default="http://localhost:8090")
            p.add_argument("--max-mismatches", type=int, default=20, help="stop after this many mismatches")
            p.add_argument("--out", type=Path, help="also write the report here")
    args = parser.parse_args(argv)
    return cmd_suggest(args) if args.command == "suggest" else cmd_check(args)


if __name__ == "__main__":
    raise SystemExit(main())

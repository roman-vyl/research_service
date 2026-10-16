"""``research-candidate-runtime-export-v1``: create-only export of a candidate to the Runtime catalog."""

from __future__ import annotations

import errno
import json
import multiprocessing
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_candidates import URL, _listed, _setup, _star

from research_service.adapters.experiments import candidates as candidates_module
from research_service.adapters.experiments import runtime_export as rx
from research_service.adapters.experiments.runtime_export import (
    RuntimeCatalogExport,
    file_name,
    runtime_identity,
    scan_catalog,
    spec_identity,
)
from research_service.domain.errors import RuntimeExportError

WITH_RUN = {"width": 3, "lookback": 20, "sl": 6}
WITH_RUN_2 = {"width": 3, "lookback": 30, "sl": 6}
REPLAY = {"width": 4, "lookback": 20, "sl": 6}
PINNED_SPEC = {"b": [1, 2.5, {"é": "ü"}], "a": {"x": True, "y": None}}
PINNED_ID = "ema_pullback:8b759fca0c11a328d43c294d"  # produced by strategy_runtime derive_strategy_instance_id


def _runtime_accepts(document: Any) -> bool:
    """A copy of the acceptance rules of Strategy Runtime's FilesystemDeploymentCatalog."""
    if not isinstance(document, dict):
        return False
    if any(f in document for f in ("strategy_instance_id", "strategy_version", "compatibility_profile")):
        return False
    if not isinstance(document.get("enabled"), bool):
        return False
    for f in ("ticker", "base_timeframe", "strategy_id"):
        if not isinstance(document.get(f), str) or not document[f].strip():
            return False
    return isinstance(document.get("raw_spec"), dict)


def _env(tmp_path: Path) -> tuple[TestClient, Path, Path]:
    catalog = tmp_path / "specs"
    catalog.mkdir()
    client, _ids, _ratio = _setup(tmp_path, catalog)
    return client, catalog, tmp_path / "analysis"


def _export(client: TestClient, candidate_id: str) -> Any:
    return client.post(f"{URL}/{candidate_id}/runtime-export")


def _files(catalog: Path) -> dict[str, tuple[bytes, int]]:
    return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in catalog.iterdir() if p.is_file()}


def _record(ticker: str = "BTCUSDT.P", spec_extra: dict[str, Any] | None = None, cid: str = "cand_" + "a" * 24) -> dict[str, Any]:
    spec = {"strategy_id": "ema_pullback", "ticker": ticker, "base_timeframe": "5m", "raw_spec": {"k": 1, **(spec_extra or {})}}
    return {
        "candidate_id": cid, "experiment_id": "e", "coords": {"w": "3"},
        "snapshot": {"run_id": "run_x"}, "strategy_spec_snapshot": {"source": "run_request", "run_id": "run_x", "spec": spec},
    }


# --- identity -------------------------------------------------------------------


def test_identity_pinned_against_runtime_and_independent_of_provenance() -> None:
    assert runtime_identity("ema_pullback", "BTCUSDT.P", "5m", PINNED_SPEC) == PINNED_ID
    base = {"strategy_id": "ema_pullback", "ticker": "BTCUSDT.P", "base_timeframe": "5m", "raw_spec": PINNED_SPEC}
    assert spec_identity(base) == spec_identity({**base, "enabled": True, "research_source": {"a": 1}}) == PINNED_ID


# --- content, listing, record ----------------------------------------------------


def test_export_writes_disabled_file_and_lists_presence(tmp_path: Path) -> None:
    client, catalog, analysis = _env(tmp_path)
    cand = _star(client, WITH_RUN)
    before = (analysis / "candidates.json").read_bytes()
    assert _listed(client)[0]["current"]["runtime"] == {"present": False}
    resp = _export(client, cand["candidate_id"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["file"] == f"btcusdt_p-{cand['candidate_id']}.json" and body["enabled"] is False and body["journal"] == "ok"
    document = json.loads((catalog / body["file"]).read_text())
    snapshot_spec = cand["strategy_spec_snapshot"]["spec"]
    assert document["enabled"] is False and _runtime_accepts(document)
    for key in ("strategy_id", "ticker", "base_timeframe", "raw_spec"):
        assert document[key] == snapshot_spec[key]
    assert not {"strategy_instance_id", "strategy_version", "compatibility_profile"} & set(document)
    assert document["research_source"]["candidate_id"] == cand["candidate_id"]
    assert document["research_source"]["run_id"] == cand["snapshot"]["run_id"]
    assert spec_identity(document) == body["strategy_instance_id"]
    assert (analysis / "candidates.json").read_bytes() == before
    actions = [json.loads(x)["action"] for x in (analysis / "candidates_journal.jsonl").read_text().splitlines()]
    assert actions == ["star", "runtime_export"]
    assert "runtime" not in json.dumps(json.loads((analysis / "candidates.json").read_text()))
    assert _listed(client)[0]["current"]["runtime"] == {"present": True, "file": body["file"], "enabled": False}
    document["enabled"] = True  # switched on outside Research
    (catalog / body["file"]).write_text(json.dumps(document))
    assert _listed(client)[0]["current"]["runtime"]["enabled"] is True


def test_body_or_query_is_rejected_and_nothing_written(tmp_path: Path) -> None:
    client, catalog, _ = _env(tmp_path)
    cid = _star(client, WITH_RUN)["candidate_id"]
    assert client.post(f"{URL}/{cid}/runtime-export", json={"enabled": True}).status_code == 422
    assert client.post(f"{URL}/{cid}/runtime-export?enabled=true").status_code == 422
    assert list(catalog.iterdir()) == []


def test_no_other_route_writes_to_the_catalog(tmp_path: Path) -> None:
    client, _, _ = _env(tmp_path)
    paths = client.get("/openapi.json").json()["paths"]
    mutating = {(path, m.upper()) for path, ops in paths.items() for m in ops if m in {"post", "put", "patch", "delete"}}
    runtime_routes = {x for x in mutating if "runtime" in x[0]}
    assert runtime_routes == {("/api/research/candidates/{candidate_id}/runtime-export", "POST")}


def test_replay_candidate_and_unknown_candidate(tmp_path: Path) -> None:
    client, catalog, _ = _env(tmp_path)
    cid = _star(client, REPLAY)["candidate_id"]
    resp = _export(client, cid)
    assert resp.status_code == 409 and resp.json()["error"] == "no_strategy_spec"
    assert _listed(client)[0]["current"]["runtime"] is None
    assert _export(client, "cand_" + "0" * 24).status_code == 404
    assert list(catalog.iterdir()) == []


def test_unset_catalog_is_503_and_listing_works(tmp_path: Path) -> None:
    client, _ids, _ = _setup(tmp_path)
    cid = _star(client, WITH_RUN)["candidate_id"]
    resp = _export(client, cid)
    assert resp.status_code == 503 and resp.json()["error"] == "runtime_catalog_unconfigured"
    assert _listed(client)[0]["current"]["runtime"] is None


def test_missing_catalog_directory_is_503_and_not_created(tmp_path: Path) -> None:
    catalog = tmp_path / "specs"
    client, _ids, _ = _setup(tmp_path, catalog)
    cid = _star(client, WITH_RUN)["candidate_id"]
    resp = _export(client, cid)
    assert resp.status_code == 503 and resp.json()["error"] == "runtime_catalog_unavailable"
    assert not catalog.exists()


# --- catalog rules ----------------------------------------------------------------


def test_repeat_export_is_duplicate(tmp_path: Path) -> None:
    client, catalog, _ = _env(tmp_path)
    cid = _star(client, WITH_RUN)["candidate_id"]
    first = _export(client, cid).json()["file"]
    again = _export(client, cid)
    assert again.status_code == 409 and again.json()["error"] == "runtime_duplicate"
    assert again.json()["details"]["files"] == [first]
    assert len(list(catalog.iterdir())) == 1


def test_hand_written_file_with_other_formatting_is_duplicate(tmp_path: Path) -> None:
    client, catalog, _ = _env(tmp_path)
    cand = _star(client, WITH_RUN)
    spec = cand["strategy_spec_snapshot"]["spec"]
    hand = {"raw_spec": spec["raw_spec"], "enabled": True, "base_timeframe": spec["base_timeframe"],
            "ticker": spec["ticker"], "strategy_id": spec["strategy_id"], "note": "mine"}
    (catalog / "mine.json").write_text(json.dumps(hand, indent=4, sort_keys=True))
    resp = _export(client, cand["candidate_id"])
    assert resp.status_code == 409 and resp.json()["details"]["files"] == ["mine.json"]
    assert [p.name for p in catalog.iterdir()] == ["mine.json"]


def test_neighbours_runtime_ignores_do_not_block_or_count(tmp_path: Path) -> None:
    client, catalog, _ = _env(tmp_path)
    cand = _star(client, WITH_RUN)
    spec = cand["strategy_spec_snapshot"]["spec"]
    (catalog / "broken.json").write_text("{not json")
    (catalog / "nan.json").write_text('{"enabled": true, "x": NaN}')
    (catalog / ".hidden.json").write_text(json.dumps({"enabled": True, **spec}))
    (catalog / "UPPER.JSON").write_text(json.dumps({"enabled": True, **spec}))
    (catalog / "sub").mkdir()
    (catalog / "sub" / "nested.json").write_text(json.dumps({"enabled": True, **spec}))
    (catalog / "rejected.json").write_text(json.dumps({"enabled": "true", **spec}))
    (catalog / "forbidden.json").write_text(json.dumps({"enabled": True, "strategy_version": "1", **spec}))
    (catalog / "list.json").write_text("[]")
    resp = _export(client, cand["candidate_id"])
    assert resp.status_code == 201, resp.text
    assert _runtime_accepts(json.loads((catalog / resp.json()["file"]).read_text()))


def test_existing_files_are_never_touched(tmp_path: Path) -> None:
    client, catalog, _ = _env(tmp_path)
    cand = _star(client, WITH_RUN)
    (catalog / "a.json").write_text(json.dumps({"enabled": True, "ticker": "X", "base_timeframe": "5m", "strategy_id": "s", "raw_spec": {}}))
    (catalog / "broken.json").write_text("{")
    before = _files(catalog)
    assert _export(client, cand["candidate_id"]).status_code == 201
    assert _export(client, cand["candidate_id"]).status_code == 409
    after = _files(catalog)
    assert {k: after[k] for k in before} == before


# --- concurrency ------------------------------------------------------------------


def _export_in_process(args: tuple[str, str, str, dict[str, Any], str]) -> str:
    catalog, lock_dir, ticker, spec_extra, cid = args
    try:
        RuntimeCatalogExport(Path(catalog), Path(lock_dir)).export(_record(ticker, spec_extra, cid))
        return "ok"
    except RuntimeExportError as exc:
        return exc.code


def test_concurrent_processes_same_identity_publish_one_file(tmp_path: Path) -> None:
    catalog, lock = tmp_path / "specs", tmp_path / "lock"
    catalog.mkdir()
    lock.mkdir()
    jobs = [(str(catalog), str(lock), "BTCUSDT.P", {}, "cand_" + c * 24) for c in "abcdef"]
    with multiprocessing.get_context("fork").Pool(6) as pool:
        results = pool.map(_export_in_process, jobs)
    assert sorted(results) == ["ok"] + ["runtime_duplicate"] * 5
    assert len(list(catalog.glob("*.json"))) == 1 and not list(catalog.glob(".*"))


def test_concurrent_processes_different_identities_all_publish(tmp_path: Path) -> None:
    catalog, lock = tmp_path / "specs", tmp_path / "lock"
    catalog.mkdir()
    lock.mkdir()
    jobs = [(str(catalog), str(lock), "BTCUSDT.P", {"n": i}, "cand_" + "0123456789ab"[i] * 24) for i in range(8)]
    with multiprocessing.get_context("fork").Pool(8) as pool:
        results = pool.map(_export_in_process, jobs)
    assert results == ["ok"] * 8
    files = scan_catalog(catalog)
    assert len(files) == 8 and len({f.identity for f in files}) == 8


def test_threads_same_identity_publish_one_file(tmp_path: Path) -> None:
    catalog, lock = tmp_path / "specs", tmp_path / "lock"
    catalog.mkdir()
    lock.mkdir()
    exporter = RuntimeCatalogExport(catalog, lock)
    out: list[str] = []

    def run(i: int) -> None:
        try:
            exporter.export(_record(cid="cand_" + "abcd"[i] * 24))
            out.append("ok")
        except RuntimeExportError as exc:
            out.append(exc.code)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(out) == ["ok", "runtime_duplicate", "runtime_duplicate", "runtime_duplicate"]


def test_external_writer_after_scan_is_not_overwritten_and_listing_flags_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog, lock = tmp_path / "specs", tmp_path / "lock"
    catalog.mkdir()
    lock.mkdir()
    record = _record()
    spec = record["strategy_spec_snapshot"]["spec"]
    real_scan = rx.scan_catalog

    def scan_then_external_write(directory: Path) -> Any:
        found = real_scan(directory)
        (directory / "outsider.json").write_text(json.dumps({"enabled": True, **spec}))
        return found

    monkeypatch.setattr(rx, "scan_catalog", scan_then_external_write)
    exporter = RuntimeCatalogExport(catalog, lock)
    result = exporter.export(record)
    assert (catalog / "outsider.json").exists() and (catalog / result["file"]).exists()
    status = RuntimeCatalogExport.status(exporter.snapshot(), spec)
    assert status == {"present": True, "duplicate": True, "files": sorted(["outsider.json", result["file"]])}


# --- failures ---------------------------------------------------------------------


def _no_temp(catalog: Path) -> bool:
    return not [p for p in catalog.iterdir() if p.name.startswith(".")]


def test_disk_full_while_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, catalog, _ = _env(tmp_path)
    cid = _star(client, WITH_RUN)["candidate_id"]
    monkeypatch.setattr(rx.os, "write", lambda *a: (_ for _ in ()).throw(OSError(errno.ENOSPC, "full")))
    resp = _export(client, cid)
    assert resp.status_code == 500 and resp.json()["error"] == "runtime_write_failed"
    assert list(catalog.iterdir()) == []


def test_link_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, catalog, _ = _env(tmp_path)
    cid = _star(client, WITH_RUN)["candidate_id"]
    monkeypatch.setattr(rx.os, "link", lambda *a: (_ for _ in ()).throw(PermissionError(errno.EPERM, "no")))
    resp = _export(client, cid)
    assert resp.status_code == 500 and resp.json()["error"] == "runtime_publish_failed"
    assert list(catalog.iterdir()) == []


def test_final_name_taken_is_not_overwritten(tmp_path: Path) -> None:
    client, catalog, _ = _env(tmp_path)
    cid = _star(client, WITH_RUN)["candidate_id"]
    taken = catalog / f"btcusdt_p-{cid}.json"
    taken.write_text("not a deployment")
    resp = _export(client, cid)
    assert resp.status_code == 409 and resp.json()["error"] == "runtime_file_exists"
    assert taken.read_text() == "not a deployment" and _no_temp(catalog)


def test_temp_unlink_failure_after_publish_still_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, catalog, _ = _env(tmp_path)
    cid = _star(client, WITH_RUN)["candidate_id"]
    monkeypatch.setattr(rx.os, "unlink", lambda *a: (_ for _ in ()).throw(PermissionError(errno.EPERM, "no")))
    resp = _export(client, cid)
    assert resp.status_code == 201
    assert [p.name for p in scan_catalog(catalog)] == [resp.json()["file"]]


def test_journal_failure_after_publish_is_reported_as_exported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, catalog, _ = _env(tmp_path)
    cid = _star(client, WITH_RUN)["candidate_id"]
    real = candidates_module.FilesystemCandidates._append_journal

    def failing(self: Any, action: str, record: dict[str, Any]) -> None:
        if action == "runtime_export":
            raise OSError(errno.ENOSPC, "full")
        real(self, action, record)

    monkeypatch.setattr(candidates_module.FilesystemCandidates, "_append_journal", failing)
    resp = _export(client, cid)
    assert resp.status_code == 201 and resp.json()["journal"] == "failed"
    assert (catalog / resp.json()["file"]).exists()
    again = _export(client, cid)
    assert again.status_code == 409 and again.json()["error"] == "runtime_duplicate"
    assert again.json()["details"]["files"] == [resp.json()["file"]]


# --- file name --------------------------------------------------------------------


@pytest.mark.parametrize(
    "ticker",
    ["../../etc/X", "/abs/path", ".hidden", "BTC\x00\n\tUSDT", "биткоин", "A" * 300, "...", "a/../b", "C:\\x"],
)
def test_hostile_ticker_stays_inside_catalog(tmp_path: Path, ticker: str) -> None:
    catalog, lock = tmp_path / "specs", tmp_path / "lock"
    catalog.mkdir()
    lock.mkdir()
    result = RuntimeCatalogExport(catalog, lock).export(_record(ticker))
    name = result["file"]
    assert "/" not in name and "\\" not in name and not name.startswith(".") and len(name.encode()) <= 255
    assert set(name) <= set("abcdefghijklmnopqrstuvwxyz0123456789_-.")
    assert [p.name for p in tmp_path.rglob("*.json")] == [name]
    assert (catalog / name).parent == catalog


def test_malformed_stored_candidate_id_is_refused(tmp_path: Path) -> None:
    catalog, lock = tmp_path / "specs", tmp_path / "lock"
    catalog.mkdir()
    lock.mkdir()
    for bad in ("../x", "cand_zz", "cand_" + "A" * 24, "x" * 40):
        with pytest.raises(RuntimeExportError) as err:
            RuntimeCatalogExport(catalog, lock).export(_record(cid=bad))
        assert err.value.code == "runtime_invalid_name"
    assert list(catalog.iterdir()) == []
    assert file_name("BTCUSDT.P", "cand_" + "a" * 24) == "btcusdt_p-cand_" + "a" * 24 + ".json"
    assert file_name("---", "cand_" + "a" * 24).startswith("spec-")

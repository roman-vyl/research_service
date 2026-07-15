from pathlib import Path

from tenacity import Retrying, stop_after_attempt, wait_none

from data_engine.fetcher.bybit_rest import BYBIT_CATEGORY, fetch_launch_time_ms
from data_engine.fetcher.depth_resolver import resolve_launch_time_ms
from data_engine.store import Db


class FakeInstrumentClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_instruments_info(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return {"retCode": 0, "result": {"list": [{"launchTime": "12345"}]}}


class RetryableRetCodeInstrumentClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._first = True

    def get_instruments_info(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        if self._first:
            self._first = False
            return {"retCode": 500, "result": {"list": []}}
        return {"retCode": 0, "result": {"list": [{"launchTime": "12345"}]}}


def _db(tmp_path: Path) -> Db:
    db = Db(tmp_path / "depth.sqlite")
    db.apply_ddl()
    return db


def test_resolver_reads_cached_launch_time(tmp_path: Path) -> None:
    db = _db(tmp_path)
    db.set_launch_time_ms("BTCUSDT", 111)

    def fail_fetch(symbol: str) -> int:
        raise AssertionError(f"network must not be called for {symbol}")

    assert resolve_launch_time_ms(db, "BTCUSDT", fetch_launch_time=fail_fetch) == 111


def test_resolver_fetches_and_caches_when_missing(tmp_path: Path) -> None:
    db = _db(tmp_path)

    launch_time = resolve_launch_time_ms(db, "BTCUSDT", fetch_launch_time=lambda symbol: 222)

    assert launch_time == 222
    assert db.get_launch_time_ms("BTCUSDT") == 222


def test_resolver_uses_linear_category() -> None:
    client = FakeInstrumentClient()
    retrying = Retrying(stop=stop_after_attempt(1), wait=wait_none(), reraise=True)

    fetch_launch_time_ms("BTCUSDT", client=client, retrying=retrying)

    assert client.calls[0]["category"] == BYBIT_CATEGORY == "linear"


def test_resolver_parses_launch_time_from_instruments_info() -> None:
    client = FakeInstrumentClient()
    retrying = Retrying(stop=stop_after_attempt(1), wait=wait_none(), reraise=True)

    assert fetch_launch_time_ms("BTCUSDT", client=client, retrying=retrying) == 12345


def test_resolver_retries_when_retcode_is_retryable() -> None:
    client = RetryableRetCodeInstrumentClient()
    retrying = Retrying(stop=stop_after_attempt(2), wait=wait_none(), reraise=True)

    assert fetch_launch_time_ms("BTCUSDT", client=client, retrying=retrying) == 12345
    assert len(client.calls) == 2

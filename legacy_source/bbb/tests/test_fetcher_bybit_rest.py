from tenacity import wait_none

from data_engine.contracts import FetchRequest, TimeWindow
from data_engine.fetcher.bybit_rest import BYBIT_CATEGORY, BYBIT_KLINE_LIMIT, BybitREST


def _request_tf(tf: str) -> FetchRequest:
    return FetchRequest("BTCUSDT", tf, TimeWindow(0, 3_600_000 * 2))


class FakeKlineClient:
    def __init__(self, payload: list[list[str]], fail_times: int = 0) -> None:
        self.payload = payload
        self.fail_times = fail_times
        self.calls: list[dict] = []

    def get_kline(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ConnectionError("temporary network error")
        return {"retCode": 0, "result": {"list": self.payload}}


def _request() -> FetchRequest:
    return _request_tf("1h")


def test_fetch_candles_maps_payload_to_candle() -> None:
    client = FakeKlineClient([["0", "1", "2", "0.5", "1.5", "10", "ignored"]])
    candles = BybitREST(client=client, wait=wait_none()).fetch_candles(_request())

    assert candles[0].symbol == "BTCUSDT"
    assert candles[0].timeframe == "1h"
    assert candles[0].open_time_ms == 0
    assert candles[0].open == 1.0
    assert candles[0].high == 2.0
    assert candles[0].low == 0.5
    assert candles[0].close == 1.5
    assert candles[0].volume == 10.0


def test_fetch_candles_returns_asc_order() -> None:
    client = FakeKlineClient(
        [
            ["3600000", "1", "2", "0.5", "1.5", "10", "x"],
            ["0", "1", "2", "0.5", "1.5", "10", "x"],
        ]
    )

    candles = BybitREST(client=client, wait=wait_none()).fetch_candles(_request())

    assert [candle.open_time_ms for candle in candles] == [0, 3_600_000]


def test_fetcher_retries_on_transient_errors() -> None:
    client = FakeKlineClient([["0", "1", "2", "0.5", "1.5", "10", "x"]], fail_times=2)

    candles = BybitREST(client=client, wait=wait_none()).fetch_candles(_request())

    assert len(candles) == 1
    assert len(client.calls) == 3


def test_fetcher_retries_when_retcode_is_retryable() -> None:
    class RetryableRetCodeClient(FakeKlineClient):
        def __init__(self) -> None:
            super().__init__([["0", "1", "2", "0.5", "1.5", "10", "x"]])
            self._first = True

        def get_kline(self, **kwargs: object) -> dict:
            self.calls.append(kwargs)
            if self._first:
                self._first = False
                return {"retCode": 500, "result": {"list": []}}
            return {"retCode": 0, "result": {"list": self.payload}}

    client = RetryableRetCodeClient()
    candles = BybitREST(client=client, wait=wait_none()).fetch_candles(_request())

    assert len(candles) == 1
    assert len(client.calls) == 2


def test_fetcher_uses_linear_category_constant() -> None:
    client = FakeKlineClient([])

    BybitREST(client=client, wait=wait_none()).fetch_candles(_request())

    assert client.calls[0]["category"] == BYBIT_CATEGORY == "linear"


def test_fetcher_maps_1h_to_bybit_interval_60() -> None:
    client = FakeKlineClient([])

    BybitREST(client=client, wait=wait_none()).fetch_candles(_request())

    assert client.calls[0]["interval"] == "60"


def test_fetcher_maps_5m_to_bybit_interval_5() -> None:
    client = FakeKlineClient([])

    BybitREST(client=client, wait=wait_none()).fetch_candles(_request_tf("5m"))

    assert client.calls[0]["interval"] == "5"


def test_fetcher_maps_1d_to_bybit_interval_d() -> None:
    client = FakeKlineClient([])

    BybitREST(client=client, wait=wait_none()).fetch_candles(_request_tf("1d"))

    assert client.calls[0]["interval"] == "D"


def test_fetcher_passes_end_as_window_end_minus_one() -> None:
    client = FakeKlineClient([])

    BybitREST(client=client, wait=wait_none()).fetch_candles(_request())

    assert client.calls[0]["end"] == 7_200_000 - 1


def test_fetcher_uses_explicit_limit() -> None:
    client = FakeKlineClient([])

    BybitREST(client=client, wait=wait_none()).fetch_candles(_request())

    assert client.calls[0]["limit"] == BYBIT_KLINE_LIMIT == 200


def test_fetcher_filters_rows_to_requested_window() -> None:
    client = FakeKlineClient(
        [
            ["-3600000", "1", "2", "0.5", "1.5", "10", "x"],
            ["0", "1", "2", "0.5", "1.5", "10", "x"],
            ["7200000", "1", "2", "0.5", "1.5", "10", "x"],
        ]
    )

    candles = BybitREST(client=client, wait=wait_none()).fetch_candles(_request())

    assert [candle.open_time_ms for candle in candles] == [0]

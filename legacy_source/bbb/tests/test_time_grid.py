import pytest

from data_engine.engine.time_grid import (
    align_to_grid,
    ceil_to_grid,
    last_closed_open_time_ms,
    next_close_ms,
    tf_ms,
)


def test_tf_ms_known_values() -> None:
    assert tf_ms("5m") == 300_000
    assert tf_ms("15m") == 900_000
    assert tf_ms("1h") == 3_600_000
    assert tf_ms("4h") == 14_400_000
    assert tf_ms("1d") == 86_400_000


def test_tf_ms_rejects_unknown_tf() -> None:
    with pytest.raises(ValueError):
        tf_ms("1m")
    with pytest.raises(ValueError):
        tf_ms("2d")


def test_align_to_grid_rounds_down() -> None:
    assert align_to_grid(3_600_000 + 123_456, "1h") == 3_600_000


def test_ceil_to_grid_rounds_up() -> None:
    assert ceil_to_grid(3_600_000 + 1, "1h") == 7_200_000
    assert ceil_to_grid(3_600_000, "1h") == 3_600_000


def test_next_close_ms() -> None:
    assert next_close_ms(3_600_000 + 1, "1h") == 7_200_000


def test_last_closed_open_time_ms() -> None:
    assert last_closed_open_time_ms(7_200_000, "1h") == 3_600_000
    assert last_closed_open_time_ms(7_200_000 + 1, "1h") == 3_600_000

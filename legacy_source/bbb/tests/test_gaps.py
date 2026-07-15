from data_engine.contracts import TimeWindow
from data_engine.contracts.gap import Gap
from data_engine.engine.gaps import find_gaps_linear


def test_find_gaps_empty_timestamps_returns_full_window_gap() -> None:
    window = TimeWindow(0, 5_000)
    assert find_gaps_linear([], 1_000, window) == [Gap(0, 5_000)]


def test_find_gaps_complete_grid_returns_empty_list() -> None:
    window = TimeWindow(0, 5_000)
    assert find_gaps_linear([0, 1_000, 2_000, 3_000, 4_000], 1_000, window) == []


def test_find_gaps_leading_gap() -> None:
    window = TimeWindow(0, 5_000)
    assert find_gaps_linear([2_000, 3_000, 4_000], 1_000, window) == [Gap(0, 2_000)]


def test_find_gaps_middle_gap() -> None:
    window = TimeWindow(0, 5_000)
    assert find_gaps_linear([0, 3_000, 4_000], 1_000, window) == [Gap(1_000, 3_000)]


def test_find_gaps_trailing_gap() -> None:
    window = TimeWindow(0, 5_000)
    assert find_gaps_linear([0, 1_000, 2_000], 1_000, window) == [Gap(3_000, 5_000)]


def test_find_gaps_multiple_gaps() -> None:
    window = TimeWindow(0, 8_000)
    assert find_gaps_linear([0, 2_000, 5_000, 7_000], 1_000, window) == [Gap(1_000, 2_000), Gap(3_000, 5_000), Gap(6_000, 7_000)]


def test_find_gaps_collapses_adjacent_missing_timestamps() -> None:
    window = TimeWindow(0, 5_000)
    assert find_gaps_linear([0, 3_000, 4_000], 1_000, window) == [Gap(1_000, 3_000)]


def test_find_gaps_ignores_duplicates() -> None:
    window = TimeWindow(0, 5_000)
    assert find_gaps_linear([0, 0, 1_000, 3_000, 3_000, 4_000], 1_000, window) == [Gap(2_000, 3_000)]


def test_find_gaps_accepts_unsorted_timestamps() -> None:
    window = TimeWindow(0, 5_000)
    assert find_gaps_linear([4_000, 0, 3_000, 1_000], 1_000, window) == [Gap(2_000, 3_000)]


def test_find_gaps_ignores_timestamps_outside_window() -> None:
    window = TimeWindow(0, 5_000)
    assert find_gaps_linear([-1_000, 0, 1_000, 4_000, 6_000], 1_000, window) == [Gap(2_000, 4_000)]

"""Lossless columnar candle storage (`research-compact-market-frame-v1`).

A full 5m window holds about 685k candles. As pydantic `Candle` objects with five
`Decimal` fields that costs about 1.1 GB; here each value is an `int64` coefficient
plus an `int8` exponent (about 36 MB), and the exact `Decimal` -- sign, digits and
exponent, so `6500` and `6500.0` stay distinct -- is rebuilt only for the candle that
is read. No float is involved.
"""

from __future__ import annotations

from array import array
from collections.abc import Iterable, Iterator, Mapping, Sequence
from decimal import MAX_EMAX, MIN_EMIN, Context, Decimal
from typing import TYPE_CHECKING, Any, overload

if TYPE_CHECKING:
    from research_service.domain.contracts import Candle

_FIELDS = ("open", "high", "low", "close", "volume")
_CANDLE_FIELDS = frozenset(("open_time_ms", *_FIELDS))
_new = object.__new__
_set = object.__setattr__
_INT64_MAX = 2**63 - 1


def _parse(text: str, index: int, name: str) -> tuple[int, int]:
    """Coefficient and exponent of a plain decimal string, as `Decimal(text)` has them;
    anything else (exponent notation, junk) goes through `Decimal` itself."""
    body = text[1:] if text[:1] == "-" else text
    whole, dot, fraction = body.partition(".")
    if whole.isdigit() and (not dot or fraction.isdigit() or fraction == "") and whole.isascii() and fraction.isascii():
        coefficient = int(whole + fraction)
        if coefficient > _INT64_MAX or len(fraction) > 128:
            return _split(Decimal(text))
        if text[:1] == "-":
            if coefficient == 0:
                raise ValueError("negative zero is not a candle value")
            coefficient = -coefficient
        return coefficient, -len(fraction)
    try:
        return _split(Decimal(text))
    except ArithmeticError as exc:
        raise ValueError(f"candle {index}: {name} is not a decimal") from exc


def _split(value: Decimal) -> tuple[int, int]:
    sign, digits, exponent = value.as_tuple()
    if not isinstance(exponent, int):
        raise ValueError(f"candle value is not finite: {value}")
    if not -128 <= exponent <= 127:
        raise ValueError(f"candle value exponent out of range: {value}")
    coefficient = int("".join(map(str, digits))) if digits else 0
    if coefficient > _INT64_MAX:
        raise ValueError(f"candle value has too many digits: {value}")
    if sign:
        if coefficient == 0:
            raise ValueError("negative zero is not a candle value")
        coefficient = -coefficient
    return coefficient, exponent


# Exact for every stored value: coefficients have at most 19 digits, and a private
# context keeps any caller-side context change out of the rebuild.
_EXACT = Context(prec=40, Emax=MAX_EMAX, Emin=MIN_EMIN)


def _join(coefficient: int, exponent: int) -> Decimal:
    return Decimal(coefficient).scaleb(exponent, _EXACT)


def _candle_type() -> type[Candle]:
    # `contracts` defines `MarketFrame` on top of this module, so import lazily.
    from research_service.domain.contracts import Candle

    return Candle


class CandleColumns(Sequence["Candle"]):
    """Read-only sequence of `Candle` backed by fixed-width arrays."""

    __slots__ = ("_times", "_coef", "_exp")

    def __init__(self) -> None:
        self._times = array("q")
        self._coef = {name: array("q") for name in _FIELDS}
        self._exp = {name: array("b") for name in _FIELDS}

    # --- building ---------------------------------------------------------------

    def _append(self, open_time_ms: int, values: Mapping[str, Decimal]) -> None:
        self._times.append(open_time_ms)
        for name in _FIELDS:
            coefficient, exponent = _split(values[name])
            self._coef[name].append(coefficient)
            self._exp[name].append(exponent)

    @classmethod
    def from_candles(cls, candles: Iterable[Candle]) -> CandleColumns:
        columns = cls()
        for candle in candles:
            columns._append(candle.open_time_ms, {name: getattr(candle, name) for name in _FIELDS})
        return columns

    @classmethod
    def from_wire(cls, items: Iterable[Any]) -> CandleColumns:
        """Candles exactly as MDS sends them (objects with `open_time_ms` and the five
        values as decimal strings), validated like `Candle`, without one model each."""
        columns = cls()
        expected_keys = {"open_time_ms", *_FIELDS}
        for index, item in enumerate(items):
            if not isinstance(item, Mapping) or set(item) != expected_keys:
                raise ValueError(f"candle {index} must have exactly the fields {sorted(expected_keys)}")
            open_time_ms = item["open_time_ms"]
            if isinstance(open_time_ms, bool) or not isinstance(open_time_ms, int) or open_time_ms < 0:
                raise ValueError(f"candle {index}: open_time_ms must be a non-negative integer")
            columns._times.append(open_time_ms)
            for name in _FIELDS:
                raw = item[name]
                if isinstance(raw, bool) or not isinstance(raw, str | int | float):
                    raise ValueError(f"candle {index}: {name} is not a decimal")
                coefficient, exponent = _parse(str(raw), index, name)
                columns._coef[name].append(coefficient)
                columns._exp[name].append(exponent)
        return columns

    # --- access -----------------------------------------------------------------

    def open_times(self) -> Sequence[int]:
        return self._times

    def _candle(self, index: int) -> Candle:
        # The same state `Candle.model_construct` sets, without its per-call overhead:
        # this runs once per bar read in the execution loops. Values are already exact.
        coef, exp = self._coef, self._exp
        candle_type = _candle_type()
        candle = _new(candle_type)
        _set(
            candle,
            "__dict__",
            {
                "open_time_ms": self._times[index],
                "open": _join(coef["open"][index], exp["open"][index]),
                "high": _join(coef["high"][index], exp["high"][index]),
                "low": _join(coef["low"][index], exp["low"][index]),
                "close": _join(coef["close"][index], exp["close"][index]),
                "volume": _join(coef["volume"][index], exp["volume"][index]),
            },
        )
        _set(candle, "__pydantic_fields_set__", set(_CANDLE_FIELDS))
        _set(candle, "__pydantic_extra__", None)
        _set(candle, "__pydantic_private__", None)
        return candle

    def __len__(self) -> int:
        return len(self._times)

    @overload
    def __getitem__(self, index: int) -> Candle: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Candle, ...]: ...

    def __getitem__(self, index: int | slice) -> Candle | tuple[Candle, ...]:
        if isinstance(index, slice):
            return tuple(self._candle(i) for i in range(*index.indices(len(self))))
        n = len(self)
        if index < 0:
            index += n
        if not 0 <= index < n:
            raise IndexError("candle index out of range")
        return self._candle(index)

    def __iter__(self) -> Iterator[Candle]:
        for i in range(len(self)):
            yield self._candle(i)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CandleColumns):
            return (
                self._times == other._times
                and self._coef == other._coef
                and self._exp == other._exp
            )
        if isinstance(other, Sequence) and not isinstance(other, str | bytes):
            return len(self) == len(other) and all(a == b for a, b in zip(self, other, strict=True))
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"CandleColumns(len={len(self)})"

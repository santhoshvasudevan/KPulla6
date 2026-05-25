from datetime import date

import pytest

from finance.performance_range import (
    InvalidPerformanceRangeError,
    resolve_performance_range_start,
    validate_performance_range,
)


def test_validate_performance_range_default():
    assert validate_performance_range(None) == "1Y"


def test_validate_performance_range_invalid():
    with pytest.raises(InvalidPerformanceRangeError):
        validate_performance_range("bogus")


def test_resolve_range_start_1y():
    today = date(2026, 5, 10)
    inception = date(2020, 1, 1)
    start = resolve_performance_range_start("1Y", today, inception)
    assert start == date(2025, 5, 10)


def test_resolve_range_start_ytd():
    today = date(2026, 5, 10)
    inception = date(2020, 1, 1)
    assert resolve_performance_range_start("YTD", today, inception) == date(2026, 1, 1)


def test_resolve_range_clamped_to_inception():
    today = date(2026, 5, 10)
    inception = date(2026, 4, 1)
    start = resolve_performance_range_start("1Y", today, inception)
    assert start == inception

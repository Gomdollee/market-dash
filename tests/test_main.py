from datetime import date

import pytest

from market_dash.main import _month_range


@pytest.mark.parametrize(
    "today, ahead, expected",
    [
        (date(2026, 11, 8), 2, (date(2026, 11, 1), date(2027, 1, 31))),
        (date(2026, 1, 31), 1, (date(2026, 1, 1), date(2026, 2, 28))),
        (date(2026, 12, 15), 0, (date(2026, 12, 1), date(2026, 12, 31))),
    ],
)
def test_month_range(today, ahead, expected):
    assert _month_range(today, ahead) == expected

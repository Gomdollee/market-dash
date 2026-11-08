from datetime import date

from market_dash.sources.events import fomc_event, parse_fomc


def _meeting(month, day):
    return (
        f'<div class="fomc-meeting__month col-xs-5"><strong>{month}</strong></div>'
        f'<div class="fomc-meeting__date col-xs-4">{day}</div>'
    )


HTML = (
    '<h4><a id="1">2027 FOMC Meetings</a></h4>'
    + _meeting("January", "26-27")
    + _meeting("Apr/May", "30-1")
    + '<h4><a id="2">2026 FOMC Meetings</a></h4>'
    + _meeting("March", "17-18*")
    + _meeting("May", "22 (notation vote)")
    + _meeting("Oct/Nov", "31-1*")
)


def test_parse_fomc():
    assert parse_fomc(HTML) == [
        {"date": date(2026, 3, 18), "sep": True},
        {"date": date(2026, 11, 1), "sep": True},
        {"date": date(2027, 1, 27), "sep": False},
        {"date": date(2027, 5, 1), "sep": False},
    ]


def test_fomc_event_converts_to_kst():
    e = fomc_event({"date": date(2026, 12, 9), "sep": True})  # 겨울: 14:00 ET = 04:00 KST 다음 날
    assert e["detail"] == "성명 14:00 ET (한국 12/10 04:00)"
    assert "점도표" in e["title"]

"""Security PUSH ``rtlog`` parsing for access-control panels."""

from __future__ import annotations

from app.adms.parser import parse_rtlog


def test_rtlog_maps_access_event_to_attendance() -> None:
    body = (
        "time=2024-03-15 08:30:00\tpin=1001\tcardno=0\teventaddr=1\t"
        "event=27\tinoutstatus=1\tverifytype=15\tindex=21"
    )
    records, stats = parse_rtlog(body, "ACC001", "America/Mexico_City")
    assert stats.valid == 1
    assert stats.skipped == 0
    assert records[0].user_id == "1001"
    assert records[0].status == 1
    assert records[0].verify_mode == 15
    assert records[0].work_code == ""
    assert str(records[0].timestamp.tzinfo) == "America/Mexico_City"


def test_rtlog_skips_rows_without_pin_or_timestamp() -> None:
    body = "time=2024-03-15 08:30:00\tpin=\n\npin=1\ttime=bad"
    records, stats = parse_rtlog(body, "ACC001")
    assert records == []
    assert (stats.total, stats.valid, stats.skipped) == (2, 0, 2)

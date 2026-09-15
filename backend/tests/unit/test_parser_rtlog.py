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


def test_rtlog_parses_speedface_v5l_capture() -> None:
    """Actual Security PUSH payloads captured from the deployed V5L."""
    body = (
        "time=2026-09-15 15:32:41\tpin=2\tcardno=0\teventaddr=1\tevent=3\t"
        "inoutstatus=0\tverifytype=1\tindex=114\tsitecode=0\tlinkid=0\t"
        "maskflag=255\ttemperature=255\tconvtemperature=255\n"
        "time=2026-09-15 15:33:07\tpin=2\tcardno=0\teventaddr=1\tevent=3\t"
        "inoutstatus=0\tverifytype=1\tindex=115\tsitecode=0\tlinkid=0\t"
        "maskflag=255\ttemperature=255\tconvtemperature=255\n"
        "time=2026-09-15 15:33:16\tpin=5\tcardno=0\teventaddr=1\tevent=3\t"
        "inoutstatus=0\tverifytype=15\tindex=116\tsitecode=0\tlinkid=0\t"
        "maskflag=255\ttemperature=255\tconvtemperature=255\n"
        "time=2026-09-15 15:33:17\tpin=5\tcardno=0\teventaddr=1\tevent=3\t"
        "inoutstatus=0\tverifytype=15\tindex=117\tsitecode=0\tlinkid=0\t"
        "maskflag=255\ttemperature=255\tconvtemperature=255"
    )
    records, stats = parse_rtlog(body, "AJE1260401355", "America/Mexico_City")
    assert (stats.total, stats.valid, stats.skipped) == (4, 4, 0)
    assert [(r.user_id, r.status, r.verify_mode) for r in records] == [
        ("2", 0, 1),
        ("2", 0, 1),
        ("5", 0, 15),
        ("5", 0, 15),
    ]
    assert [r.timestamp.second for r in records] == [41, 7, 16, 17]

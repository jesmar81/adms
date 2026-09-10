"""ATTLOG parser tests (valid, epoch, malformed, defaults)."""

from __future__ import annotations

from datetime import UTC

from app.adms.parser import parse_attlog


def test_attlog_two_valid_lines() -> None:
    body = "1001\t2024-03-15 08:30:00\t0\t1\t\n1002\t2024-03-15 08:31:00\t1\t4\tWC01"
    records, stats = parse_attlog(body, "TEST001", "UTC")
    assert len(records) == 2
    assert stats.skipped == 0
    assert records[0].user_id == "1001"
    assert records[0].status == 0
    assert records[0].verify_mode == 1
    assert records[0].work_code == ""
    assert records[1].work_code == "WC01"
    assert records[0].timestamp.tzinfo is not None


def test_attlog_epoch_timestamp() -> None:
    records, _ = parse_attlog("1001\t1710487800\t0\t1\t", "S1", "UTC")
    assert len(records) == 1
    assert records[0].timestamp.tzinfo == UTC


def test_attlog_minimal_fields_default_rest() -> None:
    records, _ = parse_attlog("1001\t2024-03-15 08:30:00", "S1", "UTC")
    assert len(records) == 1
    assert (records[0].status, records[0].verify_mode, records[0].work_code) == (0, 0, "")


def test_attlog_malformed_lines_skipped() -> None:
    body = "\n".join(
        [
            "1001\t2024-03-15 08:30:00\t0\t1\t",
            "onlyonefield",
            "\t2024-03-15 08:30:00\t0\t1\t",
            "1003\tnot-a-timestamp\t0\t1\t",
            "1004\t2024-03-15 08:31:00\tNaN\tNaN\t",
        ]
    )
    records, stats = parse_attlog(body, "S1", "UTC")
    pins = {r.user_id for r in records}
    assert pins == {"1001", "1004"}
    assert stats.skipped == 3
    # Non-integer status/verify default to 0 without skipping.
    rec = next(r for r in records if r.user_id == "1004")
    assert (rec.status, rec.verify_mode) == (0, 0)


def test_attlog_device_timezone_applied() -> None:
    records, _ = parse_attlog("1\t2024-03-15 08:30:00", "S1", "America/Mexico_City")
    assert str(records[0].timestamp.tzinfo) == "America/Mexico_City"


def test_attlog_invalid_timezone_falls_back_utc() -> None:
    records, _ = parse_attlog("1\t2024-03-15 08:30:00", "S1", "Not/AZone")
    assert len(records) == 1

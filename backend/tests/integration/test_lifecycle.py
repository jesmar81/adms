"""P2 regression: M-02 timezone, M-03 lifecycle, M-04 failure semantics, M-08 IDs."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core import security
from app.core.database import get_db
from app.main import create_app


@pytest_asyncio.fixture
async def life_client(db_session):  # type: ignore[no-untyped-def]
    from app.models.user import User

    user = User(
        username="life",
        email="life@example.com",
        password_hash=security.hash_password("s3cret-pw!"),
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.commit()

    app = create_app()

    async def _override():  # type: ignore[no-untyped-def]
        yield db_session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "life", "password": "s3cret-pw!"}
        )
        assert login.status_code == 200
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield client
    app.dependency_overrides.clear()


async def _device_id(life_client, serial: str) -> str:  # type: ignore[no-untyped-def]
    await life_client.post(f"/iclock/registry?SN={serial}", content="~DeviceName=D")
    devices = (await life_client.get("/api/v1/devices")).json()
    return str(next(d for d in devices if d["serial_number"] == serial)["id"])


async def _drain(life_client, serial: str) -> str:  # type: ignore[no-untyped-def]
    response = await life_client.get(f"/iclock/getrequest?SN={serial}")
    assert response.status_code == 200
    return response.text


# --- M-02 -----------------------------------------------------------------


async def test_patch_timezone_and_attlog_conversion(life_client) -> None:  # type: ignore[no-untyped-def]
    device_id = await _device_id(life_client, "TZ001")
    patched = await life_client.patch(
        f"/api/v1/devices/{device_id}", json={"timezone": "America/Mexico_City"}
    )
    assert patched.status_code == 200
    assert patched.json()["timezone"] == "America/Mexico_City"
    bad = await life_client.patch(f"/api/v1/devices/{device_id}", json={"timezone": "Mars/Olympus"})
    assert bad.status_code == 422
    # 08:30 in Mexico City (UTC-6, no DST in March 2024) is stored as 14:30 UTC.
    await life_client.post(
        "/iclock/cdata?SN=TZ001&table=ATTLOG", content="9\t2024-03-15 08:30:00\t0\t15\t"
    )
    rows = (await life_client.get("/api/v1/attendance?pin=9")).json()
    assert len(rows) == 1
    assert "14:30" in rows[0]["recorded_at"]
    audit = (await life_client.get("/api/v1/audit?limit=50")).json()
    assert any(a["action"] == "device.update" for a in audit)


async def test_disable_and_reenable(life_client) -> None:  # type: ignore[no-untyped-def]
    device_id = await _device_id(life_client, "REEN001")
    assert (await life_client.patch(f"/api/v1/devices/{device_id}/disable")).status_code == 200
    reenabled = await life_client.patch(f"/api/v1/devices/{device_id}", json={"status": "active"})
    assert reenabled.status_code == 200
    assert reenabled.json()["status"] != "disabled"
    assert (
        await life_client.patch(f"/api/v1/devices/{device_id}", json={"status": "explode"})
    ).status_code == 422


# --- M-03 -----------------------------------------------------------------


async def test_create_confirm_lifecycle(life_client) -> None:  # type: ignore[no-untyped-def]
    device_id = await _device_id(life_client, "LIFE001")
    created = await life_client.post(
        f"/api/v1/device-users/{device_id}",
        json={"pin": "3001", "name": "Nora", "privilege": 0, "card": ""},
    )
    assert created.json()["sync_state"] == "pending"
    wire = await _drain(life_client, "LIFE001")
    assert wire.startswith("C:1:DATA UPDATE USERINFO")
    confirm = await life_client.post(
        "/iclock/devicecmd?SN=LIFE001", content="ID=1&Return=0&CMD=DATA"
    )
    assert confirm.text == "OK"
    row = (await life_client.get(f"/api/v1/device-users?device_id={device_id}")).json()[0]
    assert row["sync_state"] == "synced"
    assert row["last_protocol_command_id"] == 1
    events = (await life_client.get(f"/api/v1/devices/{device_id}/events?limit=50")).json()
    assert any(e["type"] == "user_sync_confirmed" for e in events)


async def test_schedule_aware_reports(life_client) -> None:  # type: ignore[no-untyped-def]
    group = (
        await life_client.post("/api/v1/corporate-groups", json={"name": "R", "code": "RPT"})
    ).json()
    company = (
        await life_client.post(
            "/api/v1/companies",
            json={"corporate_group_id": group["id"], "legal_name": "Reportes"},
        )
    ).json()
    worker = (
        await life_client.post(
            "/api/v1/people",
            json={"corporate_group_id": group["id"], "first_name": "Luz", "last_name": "Paz"},
        )
    ).json()
    absent = (
        await life_client.post(
            "/api/v1/people",
            json={"corporate_group_id": group["id"], "first_name": "Sin", "last_name": "Marca"},
        )
    ).json()
    slots = [
        {"day_of_week": day, "kind": kind, "expected_at": expected}
        for day in range(5)
        for kind, expected in (("entry", "09:00"), ("exit", "18:00"))
    ]
    schedule = (
        await life_client.post(
            "/api/v1/work-schedules",
            json={"company_id": company["id"], "name": "L-V", "slots": slots},
        )
    ).json()
    for person, number in ((worker, "R-01"), (absent, "R-02")):
        employment = (
            await life_client.post(
                f"/api/v1/people/{person['id']}/employments",
                json={
                    "company_id": company["id"],
                    "employee_number": number,
                    "started_on": "2026-01-01",
                },
            )
        ).json()
        assignment = await life_client.post(
            f"/api/v1/employments/{employment['id']}/schedule-assignments",
            json={"work_schedule_id": schedule["id"], "effective_from": "2026-01-01"},
        )
        assert assignment.status_code == 201
    device_id = await _device_id(life_client, "RPT001")
    patched = await life_client.patch(
        f"/api/v1/devices/{device_id}", json={"timezone": "America/Mexico_City"}
    )
    assert patched.status_code == 200
    linked = await life_client.post(
        f"/api/v1/device-users/{device_id}",
        json={"person_id": worker["id"], "pin": "501", "name": "Luz Paz"},
    )
    assert linked.status_code == 201
    marks = await life_client.post(
        "/iclock/cdata?SN=RPT001&table=ATTLOG",
        content="501\t2026-09-14 09:15:00\t0\t15\t\n501\t2026-09-14 17:30:00\t1\t15\t",
    )
    assert marks.status_code == 200
    arrivals = await life_client.get(
        f"/api/v1/reports/daily-arrivals?company_id={company['id']}&report_date=2026-09-14"
    )
    assert arrivals.json()[0]["worker_name"] == "Luz Paz"
    absences = await life_client.get(
        f"/api/v1/reports/absences?company_id={company['id']}&report_date=2026-09-14"
    )
    assert [row["worker_name"] for row in absences.json()] == ["Sin Marca"]
    card = await life_client.get(
        f"/api/v1/reports/weekly-card?person_id={worker['id']}&week_start=2026-09-14"
    )
    assert len(card.json()["days"]) == 7
    punctuality = await life_client.get(
        f"/api/v1/reports/punctuality?company_id={company['id']}&date_from=2026-09-14&date_to=2026-09-14"
    )
    assert punctuality.json()[0]["late_minutes"] == 15
    assert punctuality.json()[0]["early_departure_minutes"] == 30


async def test_acc_security_push_blocks_unvalidated_legacy_user_wire(life_client) -> None:  # type: ignore[no-untyped-def]
    device_id = await _device_id(life_client, "ACCLOCK1")
    # Registration records the actual Security PUSH device type; legacy
    # USERINFO writes are intentionally unavailable until a V5L wire capture
    # proves its command/querydata dialect.
    await life_client.post("/iclock/registry?SN=ACCLOCK1", content="DeviceType=acc")
    response = await life_client.post(
        f"/api/v1/device-users/{device_id}",
        json={"pin": "3100", "name": "Laboratorio", "privilege": 0, "card": ""},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DEVICE_PROTOCOL_EVIDENCE_REQUIRED"


async def test_hr_calendar_profile_and_schedule_assignment(  # type: ignore[no-untyped-def]
    life_client, settings, monkeypatch
) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setattr(settings, "hr_pii_encryption_key", Fernet.generate_key().decode())
    group = (
        await life_client.post("/api/v1/corporate-groups", json={"name": "Grupo", "code": "GRP"})
    ).json()
    company = (
        await life_client.post(
            "/api/v1/companies", json={"corporate_group_id": group["id"], "legal_name": "Empresa"}
        )
    ).json()
    person = (
        await life_client.post(
            "/api/v1/people",
            json={"corporate_group_id": group["id"], "first_name": "Ana", "last_name": "López"},
        )
    ).json()
    assert person["nationality"] == "Mexicana"
    photo_bytes = b"\x89PNG\r\n\x1a\nworker-profile-photo"
    uploaded_photo = await life_client.put(
        f"/api/v1/people/{person['id']}/photo",
        files={"photo": ("worker.png", photo_bytes, "image/png")},
    )
    assert uploaded_photo.status_code == 200
    assert uploaded_photo.json()["content_type"] == "image/png"
    fetched_photo = await life_client.get(f"/api/v1/people/{person['id']}/photo")
    assert fetched_photo.status_code == 200
    assert fetched_photo.content == photo_bytes
    invalid_photo = await life_client.put(
        f"/api/v1/people/{person['id']}/photo",
        files={"photo": ("worker.svg", b"<svg />", "image/svg+xml")},
    )
    assert invalid_photo.status_code == 422
    invalid_profile = await life_client.patch(
        f"/api/v1/people/{person['id']}",
        json={"nationality": "Otra", "birth_state": "Distrito Federal"},
    )
    assert invalid_profile.status_code == 422
    updated = await life_client.patch(
        f"/api/v1/people/{person['id']}", json={"birth_date": "1990-01-02", "postal_code": "06000"}
    )
    assert updated.json()["postal_code"] == "06000"
    identifiers = await life_client.put(
        f"/api/v1/people/{person['id']}/sensitive",
        json={"curp": "LOPA900102HDFXXX01", "rfc": "LOPA900102AB1", "nss": "12345678901"},
    )
    assert identifiers.json()["curp"] == "LOPA900102HDFXXX01"
    shown_identifiers = await life_client.get(f"/api/v1/people/{person['id']}/sensitive")
    assert shown_identifiers.status_code == 200
    assert shown_identifiers.json()["nss"] == "12345678901"
    slots = [
        {"day_of_week": day, "kind": kind, "expected_at": value}
        for day in range(5)
        for kind, value in (("entry", "09:00"), ("exit", "18:00"))
    ]
    schedule = (
        await life_client.post(
            "/api/v1/work-schedules",
            json={"company_id": company["id"], "name": "L-V", "slots": slots},
        )
    ).json()
    employment = (
        await life_client.post(
            f"/api/v1/people/{person['id']}/employments",
            json={
                "company_id": company["id"],
                "employee_number": "A-01",
                "started_on": "2026-01-01",
            },
        )
    ).json()
    assignment = await life_client.post(
        f"/api/v1/employments/{employment['id']}/schedule-assignments",
        json={"work_schedule_id": schedule["id"], "effective_from": "2026-01-01"},
    )
    assert assignment.status_code == 201
    overlapping_assignment = await life_client.post(
        f"/api/v1/employments/{employment['id']}/schedule-assignments",
        json={"work_schedule_id": schedule["id"], "effective_from": "2026-01-02"},
    )
    assert overlapping_assignment.status_code == 409
    edited_employment = await life_client.put(
        f"/api/v1/employments/{employment['id']}",
        json={
            "company_id": company["id"],
            "employee_number": "A-01",
            "started_on": "2026-01-01",
            "position": "Supervisora",
            "contract_type": "Individual",
        },
    )
    assert edited_employment.status_code == 200
    assert edited_employment.json()["position"] == "Supervisora"
    second_schedule = (
        await life_client.post(
            "/api/v1/work-schedules",
            json={"company_id": company["id"], "name": "Turno B", "slots": slots},
        )
    ).json()
    replaced = await life_client.put(
        f"/api/v1/employments/{employment['id']}/schedule-assignments/current",
        json={"work_schedule_id": second_schedule["id"], "effective_from": "2026-02-01"},
    )
    assert replaced.status_code == 200
    assert replaced.json()["work_schedule_id"] == second_schedule["id"]
    assignment_history = (
        await life_client.get(f"/api/v1/employments/{employment['id']}/schedule-assignments")
    ).json()
    assert len(assignment_history) == 2
    assert next(item for item in assignment_history if item["id"] == assignment.json()["id"])[
        "effective_to"
    ] == "2026-01-31"
    assert sum(item["active"] and item["effective_to"] is None for item in assignment_history) == 1
    before_current = await life_client.put(
        f"/api/v1/employments/{employment['id']}/schedule-assignments/current",
        json={"work_schedule_id": schedule["id"], "effective_from": "2026-01-15"},
    )
    assert before_current.status_code == 409
    compensation = await life_client.put(
        f"/api/v1/employments/{employment['id']}/compensation",
        json={
            "daily_salary": "500.00",
            "integrated_daily_salary": "540.25",
            "pay_frequency": "quincenal",
            "bank_clabe": "123456789012345678",
            "imss_umf": "12",
        },
    )
    assert compensation.json()["bank_clabe"] == "123456789012345678"
    revised = await life_client.put(
        f"/api/v1/work-schedules/{schedule['id']}",
        json={"name": "L-V actualizado", "slots": slots},
    )
    assert revised.status_code == 200
    assert revised.json()["id"] != schedule["id"]
    assert (await life_client.delete(f"/api/v1/work-schedules/{schedule['id']}")).status_code == 409
    revised_id = revised.json()["id"]
    assert (await life_client.delete(f"/api/v1/work-schedules/{revised_id}")).status_code == 204
    holiday_path = f"/api/v1/companies/{company['id']}/holidays/generate?year=2026"
    generated = await life_client.post(holiday_path)
    assert generated.json() == {"year": 2026, "created": 7, "existing": 0}
    repeated = await life_client.post(holiday_path)
    assert repeated.json() == {"year": 2026, "created": 0, "existing": 7}
    custom = await life_client.post(
        "/api/v1/holidays",
        json={"company_id": company["id"], "holiday_date": "2026-12-24", "name": "Día interno"},
    )
    assert custom.status_code == 201
    retired_company = (
        await life_client.post(
            "/api/v1/companies",
            json={
                "corporate_group_id": group["id"],
                "legal_name": "Empresa retirada",
                "employer_registration": "A12-34567-89-0",
                "address": {
                    "street": "Avenida Reforma",
                    "exterior_number": "100",
                    "municipality": "Cuauhtémoc",
                    "state": "Ciudad de México",
                    "postal_code": "06600",
                },
            },
        )
    ).json()
    assert retired_company["employer_registration"] == "A12-34567-89-0"
    assert retired_company["address"]["postal_code"] == "06600"
    retired_site = (
        await life_client.post(
            "/api/v1/sites",
            json={"company_id": retired_company["id"], "name": "Sucursal retirada", "code": "RET"},
        )
    ).json()
    renamed_site = await life_client.patch(
        f"/api/v1/sites/{retired_site['id']}",
        json={
            "name": "Norte",
            "address": {
                "street": "Insurgentes Sur",
                "exterior_number": "200",
                "municipality": "Benito Juárez",
                "state": "Ciudad de México",
                "postal_code": "03100",
            },
        },
    )
    assert renamed_site.json()["name"] == "Norte"
    assert renamed_site.json()["address"]["postal_code"] == "03100"
    company_delete = await life_client.delete(f"/api/v1/companies/{retired_company['id']}")
    assert company_delete.status_code == 409
    site_delete = await life_client.delete(f"/api/v1/sites/{retired_site['id']}")
    assert site_delete.status_code == 204
    company_soft_delete = await life_client.delete(f"/api/v1/companies/{retired_company['id']}")
    assert company_soft_delete.status_code == 204
    site_challenge = (
        await life_client.post(f"/api/v1/sites/{retired_site['id']}/hard-delete-captcha")
    ).json()
    site_answer = site_challenge["prompt"].split()[3]
    assert (
        await life_client.request(
            "DELETE",
            f"/api/v1/sites/{retired_site['id']}/hard",
            json={"captcha_token": site_challenge["token"], "captcha_answer": site_answer},
        )
    ).status_code == 204
    company_challenge = (
        await life_client.post(f"/api/v1/companies/{retired_company['id']}/hard-delete-captcha")
    ).json()
    company_answer = company_challenge["prompt"].split()[3]
    assert (
        await life_client.request(
            "DELETE",
            f"/api/v1/companies/{retired_company['id']}/hard",
            json={"captcha_token": company_challenge["token"], "captcha_answer": company_answer},
        )
    ).status_code == 204


async def test_security_push_capabilities_are_evidence_based(life_client) -> None:  # type: ignore[no-untyped-def]
    device_id = await _device_id(life_client, "ACCCAPS1")
    await life_client.post("/iclock/registry?SN=ACCCAPS1", content="DeviceType=acc")
    await life_client.post(
        "/iclock/cdata?SN=ACCCAPS1&table=rtlog",
        content="time=2024-03-15 08:30:00\tpin=1\tinoutstatus=0\tverifytype=15",
    )
    await life_client.post(
        f"/api/v1/devices/{device_id}/commands", json={"command_type": "INFO", "params": {}}
    )
    await _drain(life_client, "ACCCAPS1")
    await life_client.post(
        "/iclock/devicecmd?SN=ACCCAPS1",
        content="ID=1&Return=0&CMD=INFO\n~DeviceName=SpeedFace-V5L\nFWVersion=1.1.9",
    )
    profile = (await life_client.get(f"/api/v1/devices/{device_id}/capabilities")).json()
    assert profile["profile"] == "security_push_acc"
    assert profile["confirmed"]["realtime_attendance"] is True
    assert profile["confirmed"]["info_command"] is True
    assert "QUERY_USERINFO" in profile["safe_commands"]
    assert "UPDATE_USERINFO" not in profile["safe_commands"]
    assert "user_update" in profile["blocked_operations"]
    assert "user_import" not in profile["blocked_operations"]

    # A read-only inventory request is the supervised probe; user writes stay
    # blocked until firmware-specific evidence has been reviewed.
    query = await life_client.post(
        f"/api/v1/devices/{device_id}/commands",
        json={"command_type": "QUERY_USERINFO", "params": {}},
    )
    assert query.status_code == 201
    assert query.json()["command"] == "DATA QUERY USERINFO"
    update = await life_client.post(
        f"/api/v1/devices/{device_id}/commands",
        json={"command_type": "UPDATE_USERINFO", "params": {"pin": "1", "name": "Lab"}},
    )
    assert update.status_code == 409
    assert update.json()["error"]["code"] == "DEVICE_PROTOCOL_EVIDENCE_REQUIRED"


async def test_failed_confirm_marks_failed(life_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "zkteco_command_max_attempts", 1)
    device_id = await _device_id(life_client, "LIFE002")
    created = await life_client.post(
        f"/api/v1/device-users/{device_id}",
        json={"pin": "3002", "name": "Ned", "privilege": 0, "card": ""},
    )
    assert created.status_code == 201
    await _drain(life_client, "LIFE002")
    await life_client.post("/iclock/devicecmd?SN=LIFE002", content="ID=1&Return=7&CMD=DATA")
    row = (await life_client.get(f"/api/v1/device-users?device_id={device_id}")).json()[0]
    assert row["sync_state"] == "failed"
    events = (await life_client.get(f"/api/v1/devices/{device_id}/events?limit=50")).json()
    assert any(e["type"] == "user_sync_failed" for e in events)


async def test_delete_confirmed_removes_row(life_client) -> None:  # type: ignore[no-untyped-def]
    device_id = await _device_id(life_client, "LIFE003")
    created = await life_client.post(
        f"/api/v1/device-users/{device_id}",
        json={"pin": "3003", "name": "Noa", "privilege": 0, "card": ""},
    )
    user_id = created.json()["id"]
    await _drain(life_client, "LIFE003")
    await life_client.post("/iclock/devicecmd?SN=LIFE003", content="ID=1&Return=0&CMD=DATA")
    doomed = await life_client.delete(f"/api/v1/device-users/{user_id}")
    assert doomed.status_code == 202
    assert doomed.json()["sync_state"] == "pending"
    await _drain(life_client, "LIFE003")
    await life_client.post("/iclock/devicecmd?SN=LIFE003", content="ID=2&Return=0&CMD=DATA")
    remaining = (await life_client.get(f"/api/v1/device-users?device_id={device_id}")).json()
    assert remaining == []


async def test_put_update_queues_and_confirms(life_client) -> None:  # type: ignore[no-untyped-def]
    device_id = await _device_id(life_client, "LIFE004")
    created = await life_client.post(
        f"/api/v1/device-users/{device_id}",
        json={"pin": "3004", "name": "Old", "privilege": 0, "card": ""},
    )
    user_id = created.json()["id"]
    await _drain(life_client, "LIFE004")
    await life_client.post("/iclock/devicecmd?SN=LIFE004", content="ID=1&Return=0&CMD=DATA")
    updated = await life_client.put(f"/api/v1/device-users/{user_id}", json={"name": "New"})
    assert updated.status_code == 200
    assert updated.json()["sync_state"] == "pending"
    # Second update while pending → 409.
    assert (
        await life_client.put(f"/api/v1/device-users/{user_id}", json={"name": "New2"})
    ).status_code == 409
    await _drain(life_client, "LIFE004")
    await life_client.post("/iclock/devicecmd?SN=LIFE004", content="ID=2&Return=0&CMD=DATA")
    row = (await life_client.get(f"/api/v1/device-users?device_id={device_id}")).json()[0]
    assert (row["name"], row["sync_state"]) == ("New", "synced")
    audit = (await life_client.get("/api/v1/audit?limit=100")).json()
    assert any(a["action"] == "device_user.update" for a in audit)


async def test_userinfo_push_reconciles_pending(life_client) -> None:  # type: ignore[no-untyped-def]
    device_id = await _device_id(life_client, "LIFE005")
    await life_client.post(
        f"/api/v1/device-users/{device_id}",
        json={"pin": "3005", "name": "Paz", "privilege": 0, "card": ""},
    )
    # Device answers a query with the user present → intent confirmed by push.
    await life_client.post(
        "/iclock/cdata?SN=LIFE005&table=USERINFO",
        content="PIN=3005\tName=Paz\tPrivilege=0\tCard=\tPassword=",
    )
    row = (await life_client.get(f"/api/v1/device-users?device_id={device_id}")).json()[0]
    assert row["sync_state"] == "synced"


# --- M-04 -----------------------------------------------------------------


async def test_attlog_persistence_failure_returns_500(
    life_client, postgres_failure_trigger
) -> None:  # type: ignore[no-untyped-def]
    await postgres_failure_trigger("attendance_logs", "INSERT")
    response = await life_client.post(
        "/iclock/cdata?SN=FAIL500&table=ATTLOG", content="1\t2024-03-15 08:30:00\t0\t1\t"
    )
    assert response.status_code == 500
    assert response.text != "OK"


async def test_getrequest_failure_stays_ok_and_pending(
    life_client, db_session, postgres_failure_trigger
) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.models.device import DeviceCommand

    device_id = await _device_id(life_client, "FAILOK")
    queued = await life_client.post(
        f"/api/v1/devices/{device_id}/commands", json={"command_type": "CHECK", "params": {}}
    )
    assert queued.status_code == 201
    await postgres_failure_trigger("device_commands", "UPDATE")
    response = await life_client.get("/iclock/getrequest?SN=FAILOK")
    assert response.status_code == 200
    assert response.text == "OK"
    command = await db_session.scalar(select(DeviceCommand).where(DeviceCommand.command == "CHECK"))
    assert command is not None and command.status == "pending"


async def test_duplicate_confirm_is_idempotent(life_client, db_session) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import func, select

    from app.models.device import DeviceEvent

    device_id = await _device_id(life_client, "IDEMP")
    await life_client.post(
        f"/api/v1/devices/{device_id}/commands", json={"command_type": "CHECK", "params": {}}
    )
    await _drain(life_client, "IDEMP")
    body = "ID=1&Return=0&CMD=CHECK"
    assert (await life_client.post("/iclock/devicecmd?SN=IDEMP", content=body)).text == "OK"
    assert (await life_client.post("/iclock/devicecmd?SN=IDEMP", content=body)).text == "OK"
    count = await db_session.scalar(
        select(func.count())
        .select_from(DeviceEvent)
        .where(DeviceEvent.event_type == "command_confirmed")
    )
    assert count == 1


# --- M-05 soak ---------------------------------------------------------------


async def test_attlog_soak_20k_lines(life_client) -> None:  # type: ignore[no-untyped-def]
    import time
    from datetime import UTC, datetime, timedelta

    base = datetime(2024, 3, 15, 8, 0, 0, tzinfo=UTC)
    fmt = "%Y-%m-%d %H:%M:%S"
    lines = [
        f"{(i % 50) + 1}\t{(base + timedelta(seconds=i)).strftime(fmt)}\t{i % 6}\t15\t"
        for i in range(20000)
    ]
    body = "\n".join(lines)
    started = time.monotonic()
    response = await life_client.post("/iclock/cdata?SN=SOAK001&table=ATTLOG", content=body)
    elapsed = time.monotonic() - started
    assert response.status_code == 200
    assert response.text == "OK: 20000"
    assert elapsed < 60, f"soak took {elapsed:.1f}s"
    # Re-post is fully deduplicated.
    again = await life_client.post("/iclock/cdata?SN=SOAK001&table=ATTLOG", content=body)
    assert again.text == "OK: 0"


# --- M-08 (single-node) ----------------------------------------------------


async def test_protocol_ids_monotonic_unique(life_client) -> None:  # type: ignore[no-untyped-def]
    device_id = await _device_id(life_client, "SEQ001")
    ids = []
    for _ in range(5):
        created = await life_client.post(
            f"/api/v1/devices/{device_id}/commands", json={"command_type": "CHECK", "params": {}}
        )
        ids.append(created.json()["protocol_command_id"])
    assert ids == [1, 2, 3, 4, 5]


# --- L-02 retry/TTL policy + L-01 date validation ----------------------------


async def test_failed_confirm_retries_then_fails(life_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "zkteco_command_max_attempts", 2)
    device_id = await _device_id(life_client, "RETRY001")
    await life_client.post(
        f"/api/v1/device-users/{device_id}",
        json={"pin": "4001", "name": "Rita", "privilege": 0, "card": ""},
    )
    await _drain(life_client, "RETRY001")
    # First failure → back to pending (retry), user still pending.
    await life_client.post("/iclock/devicecmd?SN=RETRY001", content="ID=1&Return=7&CMD=DATA")
    row = (await life_client.get(f"/api/v1/device-users?device_id={device_id}")).json()[0]
    assert row["sync_state"] == "pending"
    # Redelivered, fails again → attempts exhausted → failed.
    redelivered = await _drain(life_client, "RETRY001")
    assert "C:1:" in redelivered
    await life_client.post("/iclock/devicecmd?SN=RETRY001", content="ID=1&Return=7&CMD=DATA")
    row = (await life_client.get(f"/api/v1/device-users?device_id={device_id}")).json()[0]
    assert row["sync_state"] == "failed"


async def test_expired_command_never_delivered(life_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "zkteco_command_ttl_s", -1)
    device_id = await _device_id(life_client, "TTL001")
    await life_client.post(
        f"/api/v1/devices/{device_id}/commands", json={"command_type": "CHECK", "params": {}}
    )
    assert (await _drain(life_client, "TTL001")) == "OK"
    commands = (await life_client.get(f"/api/v1/devices/{device_id}/commands")).json()
    assert commands[0]["status"] == "expired"
    monkeypatch.setattr(settings, "zkteco_command_ttl_s", 86400)


async def test_attendance_date_validation(life_client) -> None:  # type: ignore[no-untyped-def]
    base = "/api/v1/attendance"
    naive = await life_client.get(base + "?date_from=2024-01-01T00:00:00")
    assert naive.status_code == 422
    inverted = await life_client.get(
        base + "?date_from=2025-01-01T00:00:00Z&date_to=2024-01-01T00:00:00Z"
    )
    assert inverted.status_code == 422
    ok_range = await life_client.get(
        base + "?date_from=2024-01-01T00:00:00Z&date_to=2025-01-01T00:00:00Z"
    )
    assert ok_range.status_code == 200

"""Critical security paths exercised only against PostgreSQL and Redis."""

from __future__ import annotations

from datetime import date

from app.core import security


async def _authenticate_superuser(pg_client, pg_session) -> None:  # type: ignore[no-untyped-def]
    from app.models.user import User

    pg_session.add(
        User(
            username="security-root",
            email="security-root@example.com",
            password_hash=security.hash_password("security-root-password"),
            is_active=True,
            is_superuser=True,
        )
    )
    await pg_session.commit()
    login = await pg_client.post(
        "/api/v1/auth/login",
        json={"username": "security-root", "password": "security-root-password"},
    )
    assert login.status_code == 200, login.text
    pg_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"


async def test_real_postgres_requires_provisioning_and_honors_disable(
    pg_client, pg_session, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "zkteco_auto_register_unknown", False)
    serial = "PG-SECURE-DEVICE"
    rejected = await pg_client.post(f"/iclock/registry?SN={serial}", content="DeviceType=acc")
    assert rejected.status_code == 403

    await _authenticate_superuser(pg_client, pg_session)
    provisioned = await pg_client.post(
        "/api/v1/devices",
        json={
            "serial_number": serial,
            "name": "Reloj de validación aislado",
            "model": "SpeedFace-V5L",
            "timezone": "America/Mexico_City",
        },
    )
    assert provisioned.status_code == 201, provisioned.text
    assert provisioned.json()["last_activity_at"] is None
    assert (
        await pg_client.post(f"/iclock/registry?SN={serial}", content="DeviceType=acc")
    ).status_code == 200
    assert (
        await pg_client.patch(f"/api/v1/devices/{provisioned.json()['id']}/disable")
    ).status_code == 200
    assert (
        await pg_client.post(
            f"/iclock/cdata?SN={serial}&table=ATTLOG",
            content="1001\t2026-09-21 08:00:00\t0\t15\t",
        )
    ).status_code == 403


async def test_real_redis_refresh_is_single_use(pg_client, pg_session) -> None:  # type: ignore[no-untyped-def]
    await _authenticate_superuser(pg_client, pg_session)
    login = await pg_client.post(
        "/api/v1/auth/login",
        json={"username": "security-root", "password": "security-root-password"},
    )
    assert login.status_code == 200, login.text
    refresh_token = login.json()["refresh_token"]
    first = await pg_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert first.status_code == 200, first.text
    replay = await pg_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert replay.status_code == 401


async def test_real_postgres_attendance_is_assigned_once_to_employment(
    pg_client, pg_session
) -> None:  # type: ignore[no-untyped-def]
    import uuid

    from app.models.device import Device, DeviceUser
    from app.models.hr import Company, CorporateGroup, Employment, Person, Site

    await _authenticate_superuser(pg_client, pg_session)
    group = CorporateGroup(id=uuid.uuid4(), name="Grupo asistencia", code="ATTENDANCE")
    pg_session.add(group)
    await pg_session.flush()
    company = Company(
        corporate_group_id=group.id,
        legal_name="Empresa asistencia",
        timezone="America/Mexico_City",
    )
    pg_session.add(company)
    await pg_session.flush()
    site = Site(
        company_id=company.id,
        name="Sucursal asistencia",
        code="ATT-SITE",
        timezone="America/Mexico_City",
    )
    person = Person(
        corporate_group_id=group.id,
        first_name="Ana",
        last_name="Prueba",
    )
    pg_session.add_all([site, person])
    await pg_session.flush()
    employment = Employment(
        person_id=person.id,
        company_id=company.id,
        site_id=site.id,
        employee_number="ATT-001",
        started_on=date(2026, 1, 1),
    )
    device = Device(
        serial_number="PG-ATTENDANCE-DEVICE",
        site_id=site.id,
        timezone="America/Mexico_City",
    )
    pg_session.add_all([employment, device])
    await pg_session.flush()
    pg_session.add(
        DeviceUser(
            device_id=device.id,
            person_id=person.id,
            pin="ATT-001",
            name="Ana Prueba",
        )
    )
    await pg_session.commit()

    received = await pg_client.post(
        "/iclock/cdata?SN=PG-ATTENDANCE-DEVICE&table=ATTLOG",
        content="ATT-001\t2026-09-21 08:00:00\t0\t15\t",
    )
    assert received.status_code == 200, received.text
    marks = await pg_client.get("/api/v1/attendance?pin=ATT-001")
    assert marks.status_code == 200, marks.text
    assert len(marks.json()) == 1
    assert marks.json()[0]["attribution_status"] == "assigned"
    assert marks.json()[0]["employment_id"] == str(employment.id)


async def test_real_postgres_overtime_requires_hr_then_direction(pg_client, pg_session) -> None:  # type: ignore[no-untyped-def]
    from app.models.user import User

    async def login_as(username: str) -> None:
        password = f"{username}-password"
        pg_session.add(
            User(
                username=username,
                email=f"{username}@example.com",
                password_hash=security.hash_password(password),
                is_active=True,
                is_superuser=True,
            )
        )
        await pg_session.commit()
        login = await pg_client.post(
            "/api/v1/auth/login", json={"username": username, "password": password}
        )
        assert login.status_code == 200, login.text
        pg_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    await login_as("overtime-requester")
    group = (
        await pg_client.post(
            "/api/v1/corporate-groups", json={"name": "Tiempo extra", "code": "OT"}
        )
    ).json()
    company = (
        await pg_client.post(
            "/api/v1/companies",
            json={"corporate_group_id": group["id"], "legal_name": "Empresa OT"},
        )
    ).json()
    person = (
        await pg_client.post(
            "/api/v1/people",
            json={"corporate_group_id": group["id"], "first_name": "Elena", "last_name": "Extra"},
        )
    ).json()
    employment = (
        await pg_client.post(
            f"/api/v1/people/{person['id']}/employments",
            json={
                "company_id": company["id"],
                "employee_number": "OT-001",
                "started_on": "2026-01-01",
            },
        )
    ).json()
    slots = [
        {"day_of_week": day, "kind": kind, "expected_at": expected}
        for day in range(5)
        for kind, expected in (("entry", "09:00"), ("exit", "18:00"))
    ]
    schedule = (
        await pg_client.post(
            "/api/v1/work-schedules",
            json={"company_id": company["id"], "name": "OT L-M", "slots": slots},
        )
    ).json()
    assignment = await pg_client.post(
        f"/api/v1/employments/{employment['id']}/schedule-assignments",
        json={"work_schedule_id": schedule["id"], "effective_from": "2026-01-01"},
    )
    assert assignment.status_code == 201, assignment.text
    device = (
        await pg_client.post(
            "/api/v1/devices",
            json={"serial_number": "PG-OVERTIME", "timezone": "America/Mexico_City"},
        )
    ).json()
    linked = await pg_client.post(
        f"/api/v1/device-users/{device['id']}",
        json={"person_id": person["id"], "pin": "OT-001", "name": "Elena Extra"},
    )
    assert linked.status_code == 201, linked.text
    marks = await pg_client.post(
        "/iclock/cdata?SN=PG-OVERTIME&table=ATTLOG",
        content=(
            "OT-001\t2026-09-21 09:00:00\t0\t15\t\n"
            "OT-001\t2026-09-21 18:45:00\t1\t15\t\n"
            "OT-001\t2026-09-22 09:00:00\t0\t15\t\n"
            "OT-001\t2026-09-22 18:00:00\t1\t15\t"
        ),
    )
    assert marks.status_code == 200, marks.text
    detected = await pg_client.post(
        f"/api/v1/reports/overtime/detect?company_id={company['id']}&date_from=2026-09-21&date_to=2026-09-22"
    )
    assert detected.status_code == 201, detected.text
    candidate = detected.json()[0]
    assert candidate["source"] == "detected"
    assert candidate["minutes"] == 45
    assert candidate["status"] == "pending_hr"
    dashboard = await pg_client.get(
        "/api/v1/reports/dashboard",
        params={"company_id": company["id"], "report_date": "2026-09-21"},
    )
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["scheduled_workers"] == 1
    assert dashboard.json()["present_workers"] == 1
    assert dashboard.json()["on_time_workers"] == 1
    assert dashboard.json()["overtime_pending_hr"] == 1
    manual = await pg_client.post(
        "/api/v1/reports/overtime/manual",
        json={
            "employment_id": employment["id"],
            "attendance_date": "2026-09-22",
            "minutes": 30,
            "reason": "Cierre de incidente documentado en bitácora.",
        },
    )
    assert manual.status_code == 201, manual.text
    assert manual.json()["source"] == "manual"
    self_review = await pg_client.post(
        f"/api/v1/reports/overtime/{candidate['id']}/review",
        json={
            "decision": "send_to_direction",
            "reviewed_minutes": 40,
            "note": "Evidencia revisada.",
        },
    )
    assert self_review.status_code == 409

    await login_as("overtime-hr")
    reviewed = await pg_client.post(
        f"/api/v1/reports/overtime/{candidate['id']}/review",
        json={
            "decision": "send_to_direction",
            "reviewed_minutes": 40,
            "note": "Evidencia revisada.",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "pending_direction"
    assert reviewed.json()["reviewed_minutes"] == 40
    self_authorization = await pg_client.post(
        f"/api/v1/reports/overtime/{candidate['id']}/authorize",
        json={"decision": "approve", "authorized_minutes": 35, "note": "Aprobado."},
    )
    assert self_authorization.status_code == 409

    await login_as("overtime-direction")
    authorized = await pg_client.post(
        f"/api/v1/reports/overtime/{candidate['id']}/authorize",
        json={"decision": "approve", "authorized_minutes": 35, "note": "Aprobado por Dirección."},
    )
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["status"] == "approved"
    assert authorized.json()["authorized_minutes"] == 35

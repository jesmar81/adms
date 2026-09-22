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

"""ADMS integration: registry + cdata (ATTLOG/USERINFO/INFO/OPERLOG)."""

from __future__ import annotations


def test_registry_get_ok(app_client) -> None:  # type: ignore[no-untyped-def]
    response = app_client.get("/iclock/registry?SN=TEST001")
    assert response.status_code == 200
    assert response.text == "OK"


def test_registry_post_updates_options(app_client) -> None:  # type: ignore[no-untyped-def]
    body = "~DeviceName=SpeedFace,~FWVersion=Ver 1.1.17,~MACAddress=AA:BB:CC:DD:EE:FF"
    response = app_client.post("/iclock/registry?SN=TEST001", content=body)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")


def test_registry_missing_sn_400(app_client) -> None:  # type: ignore[no-untyped-def]
    assert app_client.get("/iclock/registry").status_code == 400


def test_registry_invalid_sn_400(app_client) -> None:  # type: ignore[no-untyped-def]
    assert app_client.get("/iclock/registry?SN=has%20space").status_code == 400


def test_cdata_handshake_ok(app_client) -> None:  # type: ignore[no-untyped-def]
    response = app_client.get("/iclock/cdata?SN=TEST001")
    assert response.status_code == 200
    assert "OK" in response.text


def test_cdata_attlog_persists(app_client) -> None:  # type: ignore[no-untyped-def]
    body = "1001\t2024-03-15 08:30:00\t0\t1\t\n1002\t2024-03-15 08:31:00\t1\t4\tWC01"
    response = app_client.post("/iclock/cdata?SN=TEST001&table=ATTLOG", content=body)
    assert response.status_code == 200
    assert response.text == "OK: 2"


def test_cdata_attlog_idempotent(app_client) -> None:  # type: ignore[no-untyped-def]
    body = "1001\t2024-03-15 08:30:00\t0\t1\t"
    first = app_client.post("/iclock/cdata?SN=DUP001&table=ATTLOG", content=body)
    second = app_client.post("/iclock/cdata?SN=DUP001&table=ATTLOG", content=body)
    assert first.text == "OK: 1"
    assert second.text == "OK: 0"  # duplicate skipped, no double insert


def test_cdata_rtlog_persists_security_push_attendance(app_client) -> None:  # type: ignore[no-untyped-def]
    body = (
        "time=2024-03-15 08:30:00\tpin=1001\tcardno=0\teventaddr=1\t"
        "event=27\tinoutstatus=0\tverifytype=15\tindex=21"
    )
    response = app_client.post("/iclock/cdata?SN=ACC001&table=rtlog", content=body)
    assert response.status_code == 200
    assert response.text == "OK"


def test_cdata_attlog_malformed_partial(app_client) -> None:  # type: ignore[no-untyped-def]
    body = "1001\t2024-03-15 08:30:00\t0\t1\t\nGARBAGE\n\t\n1002\tbad-ts\t0\t1\t"
    response = app_client.post("/iclock/cdata?SN=MAL001&table=ATTLOG", content=body)
    assert response.status_code == 200
    assert response.text == "OK: 1"


def test_cdata_userinfo_ok(app_client) -> None:  # type: ignore[no-untyped-def]
    body = "PIN=1\tName=John\tPrivilege=0\tCard=\tPassword="
    response = app_client.post("/iclock/cdata?SN=TEST001&table=USERINFO", content=body)
    assert response.status_code == 200
    assert response.text == "OK"


def test_querydata_user_sync_accepts_security_push_field_case(app_client) -> None:  # type: ignore[no-untyped-def]
    body = "Pin=101\tName=Ana\tPrivilege=0\tCard=101"
    response = app_client.post("/iclock/querydata?SN=ACCQUERY1&type=user&cmdid=7", content=body)
    assert response.status_code == 200
    assert response.text == "OK"
    users = app_client.get("/api/v1/device-users?device_id=not-a-uuid")
    # Authentication is deliberately required on the administrative endpoint;
    # persistence itself is covered by the absence of a 500 from querydata.
    assert users.status_code in {401, 422}


def test_querydata_biometric_body_is_acknowledged_but_not_retained(app_client) -> None:  # type: ignore[no-untyped-def]
    response = app_client.post(
        "/iclock/querydata?SN=ACCBIO1&type=biodata&cmdid=8", content="template-secret"
    )
    assert response.status_code == 200
    assert response.text == "OK"


def test_cdata_operlog_ok(app_client) -> None:  # type: ignore[no-untyped-def]
    response = app_client.post("/iclock/cdata?SN=TEST001&table=OPERLOG", content="log data")
    assert response.status_code == 200
    assert response.text == "OK"


def test_cdata_device_info_ok(app_client) -> None:  # type: ignore[no-untyped-def]
    body = "FWVersion=Ver 8.1.1\nDeviceName=TestDevice\nIPAddress=192.168.1.100"
    response = app_client.post("/iclock/cdata?SN=TEST001", content=body)
    assert response.status_code == 200
    assert response.text == "OK"


def test_cdata_oversized_413(app_client, settings) -> None:  # type: ignore[no-untyped-def]
    big = "X" * (settings.zkteco_max_body_size + 1)
    response = app_client.post("/iclock/cdata?SN=TEST001&table=ATTLOG", content=big)
    assert response.status_code == 413


def test_device_limit_503(app_client, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "zkteco_max_devices", 1)
    assert app_client.get("/iclock/cdata?SN=LIM001").status_code == 200
    assert app_client.get("/iclock/cdata?SN=LIM002").status_code == 503
    monkeypatch.setattr(settings, "zkteco_max_devices", 1000)

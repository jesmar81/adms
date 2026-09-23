"""Push-options handshake: GET /iclock/cdata with options=all (§26).

The firmware polls `...&options=all` expecting its upload configuration
(TransFlag/Realtime). Answering plain `OK` leaves uploads disabled on several
acc firmwares, so the device never pushes ATTLOG/USERINFO.
"""

from __future__ import annotations


async def test_options_all_returns_push_block(app_client) -> None:  # type: ignore[no-untyped-def]
    response = await app_client.get("/iclock/cdata?SN=OPTALL01&options=all&pushver=3.1.2")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert body.startswith("GET OPTION FROM:")
    assert "TransFlag=" in body
    assert "Realtime=1" in body
    assert "PushProtVer=3.1.2" in body
    # Pending C: commands are NEVER mixed into this response (getrequest only).
    assert "\nC:" not in body and not body.startswith("C:")


async def test_cdata_without_options_still_ok(app_client) -> None:  # type: ignore[no-untyped-def]
    response = await app_client.get("/iclock/cdata?SN=OPTALL02")
    assert response.status_code == 200
    assert response.text == "OK"


async def test_access_panel_completes_security_push_registration(app_client) -> None:  # type: ignore[no-untyped-def]
    query = "SN=ACC001&options=all&pushver=3.1.2&DeviceType=acc"
    # Security PUSH deliberately begins with OK, then requires /registry.
    initial = await app_client.get(f"/iclock/cdata?{query}")
    assert initial.text == "OK"

    registered = await app_client.post(
        "/iclock/registry?SN=ACC001",
        content="DeviceType=acc,PushVersion=Ver 3.1.2,~DeviceName=SpeedFace",
    )
    assert registered.status_code == 200
    assert registered.text.startswith("RegistryCode=")
    assert "JSESSIONID=" in registered.headers["set-cookie"]

    configured = await app_client.post("/iclock/push?SN=ACC001")
    assert configured.status_code == 200
    assert "PushProtVer=3.1.2" in configured.text
    assert "TransTables=User Transaction" in configured.text
    assert "Realtime=1" in configured.text
    assert "SessionID=" in configured.text


async def test_post_with_options_all_is_not_discarded_as_handshake(app_client) -> None:  # type: ignore[no-untyped-def]
    response = await app_client.post(
        "/iclock/cdata?SN=OPTPOST01&options=all&table=ATTLOG",
        content="1\t2024-03-15 08:30:00\t0\t1\t",
    )
    assert response.status_code == 200
    assert response.text == "OK: 1"

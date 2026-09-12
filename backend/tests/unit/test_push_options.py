"""Push-options handshake: GET /iclock/cdata with options=all (§26).

The firmware polls `...&options=all` expecting its upload configuration
(TransFlag/Realtime). Answering plain `OK` leaves uploads disabled on several
acc firmwares, so the device never pushes ATTLOG/USERINFO.
"""

from __future__ import annotations


def test_options_all_returns_push_block(app_client) -> None:  # type: ignore[no-untyped-def]
    response = app_client.get("/iclock/cdata?SN=OPTALL01&options=all&pushver=3.1.2")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert body.startswith("GET OPTION FROM:")
    assert "TransFlag=" in body
    assert "Realtime=1" in body
    # Pending C: commands are NEVER mixed into this response (getrequest only).
    assert "\nC:" not in body and not body.startswith("C:")


def test_cdata_without_options_still_ok(app_client) -> None:  # type: ignore[no-untyped-def]
    response = app_client.get("/iclock/cdata?SN=OPTALL02")
    assert response.status_code == 200
    assert response.text == "OK"

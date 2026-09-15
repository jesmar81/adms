"""ADMS FastAPI router — the five protocol endpoints (§26).

All responses are `text/plain` wire format (§66). No JWT here (§27).
Every valid request: validate SN → register (idempotent) → touch activity →
persist raw payload → handle → commit.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.adms import parser as adms_parser
from app.adms.exceptions import InvalidSerialNumberError
from app.adms.serializers import (
    SecurityPushConfig,
    wire_attlog_ack,
    wire_commands,
    wire_ok,
    wire_push_options,
    wire_registry_code,
    wire_security_push_config,
    wire_security_push_options,
)
from app.adms.validators import validate_serial_number
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import DeviceLimitReachedError
from app.core.logging import get_logger
from app.core.ratelimit import check_adms_limit
from app.models.device import AdmsPayload, Device
from app.services import attendance as attendance_svc
from app.services import command as command_svc
from app.services import device as device_svc
from app.services import device_user as device_user_svc
from app.services import events as event_svc

router = APIRouter(tags=["adms"], include_in_schema=False)
log = get_logger("adms")


def _utcnow() -> datetime:
    return datetime.now(UTC)


# Device-side `Password=` credentials must never be stored retrievably (§19):
# raw bodies keep full troubleshooting value with secrets redacted. The
# SHA-256 is computed over the ORIGINAL bytes for integrity correlation.
_PASSWORD_RE = re.compile(r"(Password=)[^\t\r\n&]*")


def _redact_secrets(text: str) -> str:
    return _PASSWORD_RE.sub(r"\1***", text)


def _sn_or_error(request: Request) -> str | PlainTextResponse:
    sn = request.query_params.get("SN", "")
    if not sn:
        return PlainTextResponse("Missing SN parameter", status_code=400)
    if not validate_serial_number(sn):
        return PlainTextResponse("Invalid SN parameter", status_code=400)
    return sn


def _body_too_large(request: Request, body: bytes) -> bool:
    limit = get_settings().zkteco_max_body_size
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > limit:
                return True
        except ValueError:
            pass
    return len(body) > limit


async def _require_device(session: AsyncSession, serial: str) -> Device | PlainTextResponse:
    try:
        device, created = await device_svc.register_device(session, serial)
    except InvalidSerialNumberError:
        return PlainTextResponse("Invalid SN parameter", status_code=400)
    except DeviceLimitReachedError:
        return PlainTextResponse("Device limit reached", status_code=503)
    await device_svc.touch_activity(session, device)
    if created:
        log.info("device_registered", serial=serial)
    return device


async def _store_payload(
    session: AsyncSession,
    *,
    device: Device | None,
    endpoint: str,
    request: Request,
    body: bytes,
    data_type: str | None = None,
) -> AdmsPayload:
    raw_text = body.decode("utf-8", errors="replace")
    payload = AdmsPayload(
        device_id=device.id if device is not None else None,
        endpoint=endpoint,
        data_type=data_type,
        content_type=request.headers.get("content-type"),
        headers=dict(request.headers),
        query_params=dict(request.query_params),
        raw_body=_redact_secrets(raw_text) or None,
        body_hash=hashlib.sha256(body).hexdigest(),
        received_at=_utcnow(),
        processing_status="received",
    )
    session.add(payload)
    await session.flush()
    return payload


async def _drain_wire(session: AsyncSession, device: Device) -> str:
    rows = await command_svc.drain_for_device(session, device)
    if not rows:
        return wire_ok()
    return wire_commands([(r.protocol_command_id, r.command) for r in rows])


def _is_security_push_device(request: Request, device: Device) -> bool:
    """Whether this is an access-control Security PUSH terminal.

    ``DeviceType=acc`` is sent during the initial cdata request, before the
    registry body has been persisted, so inspect both sources.
    """
    device_type = request.query_params.get("DeviceType") or (device.options or {}).get(
        "DeviceType", ""
    )
    return str(device_type).lower() == "acc"


def _new_push_identifier() -> str:
    """Return an ASCII, 32-character identifier accepted by Security PUSH."""
    return secrets.token_hex(16)


def _security_push_kwargs(device: Device) -> SecurityPushConfig:
    """Return the common ACC configuration, retaining the persisted session."""
    settings = get_settings()
    if not device.adms_session_id:
        # This is only a defensive fallback for legacy rows created before the
        # Security PUSH migration.  Normal registration always creates it.
        device.adms_session_id = _new_push_identifier()
    return {
        "server_version": settings.zkteco_server_version,
        "server_name": settings.zkteco_server_name,
        "push_protocol_version": settings.zkteco_push_protocol_version,
        "error_delay": settings.zkteco_error_delay_s,
        "request_delay": settings.zkteco_request_delay_s,
        "trans_times": settings.zkteco_trans_times,
        "trans_interval": settings.zkteco_trans_interval_m,
        "trans_tables": settings.zkteco_trans_tables,
        "realtime": settings.zkteco_realtime,
        "session_id": device.adms_session_id,
        "timeout_sec": settings.zkteco_push_timeout_s,
    }


# ---------------------------------------------------------------------------
# /iclock/cdata
# ---------------------------------------------------------------------------


@router.api_route("/cdata", methods=["GET", "POST"])
async def handle_cdata(
    request: Request, session: AsyncSession = Depends(get_db)
) -> PlainTextResponse:
    sn = _sn_or_error(request)
    if isinstance(sn, PlainTextResponse):
        return sn
    if not await check_adms_limit(request, serial=sn, endpoint="cdata"):
        return PlainTextResponse("Rate limit exceeded", status_code=429)
    body = await request.body()
    if _body_too_large(request, body):
        return PlainTextResponse("Request body too large", status_code=413)

    device = await _require_device(session, serial=sn)
    if isinstance(device, PlainTextResponse):
        await session.rollback()
        return device

    # There are two incompatible PUSH handshakes.  Attendance terminals use
    # the legacy TransFlag block; access-control panels (DeviceType=acc) first
    # receive OK, register, then obtain Security PUSH config through /push.
    # Never treat a POST as this handshake: otherwise a device data payload
    # carrying options=all would be acknowledged and silently discarded.
    if request.method == "GET" and request.query_params.get("options", "").lower() == "all":
        device.last_cdata_at = _utcnow()
        if _is_security_push_device(request, device):
            if device.adms_registry_code:
                response = PlainTextResponse(
                    wire_security_push_options(
                        registry_code=device.adms_registry_code,
                        **_security_push_kwargs(device),
                    ),
                    status_code=200,
                )
            else:
                response = PlainTextResponse(wire_ok(), status_code=200)
        else:
            response = PlainTextResponse(
                wire_push_options(sn, trans_flag=get_settings().zkteco_trans_flag),
                status_code=200,
            )
        await session.commit()
        return response

    table = request.query_params.get("table", "").upper()
    text = body.decode("utf-8", errors="replace")
    log.debug("cdata", serial=sn, table=table, method=request.method)

    try:
        if table == "ATTLOG":
            response_text = await _handle_attlog(session, device, request, body, text)
        elif table == "RTLOG":
            response_text = await _handle_rtlog(session, device, request, body, text)
        elif table == "OPERLOG":
            payload = await _store_payload(
                session,
                device=device,
                endpoint="cdata",
                request=request,
                body=body,
                data_type="OPERLOG",
            )
            payload.processing_status = "processed"
            payload.processed_at = _utcnow()
            await event_svc.emit(
                session, device_id=device.id, event_type="operlog_received", payload={}
            )
            response_text = wire_ok()
        elif table == "USERINFO":
            response_text = await _handle_userinfo(session, device, request, text)
        elif table == "OPTIONS":
            response_text = await _handle_options(session, device, request, body, text)
        else:
            response_text = await _handle_info_or_commands(session, device, request, text)
        device.last_cdata_at = _utcnow()
        await session.commit()
    except Exception as exc:
        # M-04: device data may NOT have been stored — answer 500/"ERROR" so
        # the device retries instead of discarding. See docs/ADMS_PROTOCOL.md.
        await session.rollback()
        log.error("cdata_error", serial=sn, error=str(exc))
        return PlainTextResponse("ERROR", status_code=500)
    return PlainTextResponse(response_text, status_code=200)


async def _handle_attlog(
    session: AsyncSession, device: Device, request: Request, body: bytes, text: str
) -> str:
    payload = await _store_payload(
        session,
        device=device,
        endpoint="cdata",
        request=request,
        body=body,
        data_type="ATTLOG",
    )
    records, stats = adms_parser.parse_attlog(text, device.serial_number, device.timezone)
    inserted = await attendance_svc.ingest_records(
        session, device=device, records=records, raw_payload_id=payload.id
    )
    payload.processing_status = "processed" if not stats.skipped else "partial"
    payload.processed_at = _utcnow()
    if stats.skipped:
        payload.error_message = f"skipped {stats.skipped}/{stats.total} malformed lines"
        log.warning("attlog_malformed", serial=device.serial_number, skipped=stats.skipped)
    return wire_attlog_ack(inserted)


async def _handle_rtlog(
    session: AsyncSession, device: Device, request: Request, body: bytes, text: str
) -> str:
    """Persist Security PUSH access events as attendance records.

    ACC firmware posts this table for a biometric/card check; it does not use
    the legacy ATTLOG table.  Its acknowledgement is exactly ``OK``.
    """
    payload = await _store_payload(
        session,
        device=device,
        endpoint="cdata",
        request=request,
        body=body,
        data_type="RTLOG",
    )
    records, stats = adms_parser.parse_rtlog(text, device.serial_number, device.timezone)
    await attendance_svc.ingest_records(
        session, device=device, records=records, raw_payload_id=payload.id
    )
    payload.processing_status = "processed" if not stats.skipped else "partial"
    payload.processed_at = _utcnow()
    if stats.skipped:
        payload.error_message = f"skipped {stats.skipped}/{stats.total} malformed RTLOG lines"
        log.warning("rtlog_malformed", serial=device.serial_number, skipped=stats.skipped)
    return wire_ok()


async def _handle_userinfo(
    session: AsyncSession, device: Device, request: Request, text: str
) -> str:
    payload = await _store_payload(
        session,
        device=device,
        endpoint="cdata",
        request=request,
        body=text.encode("utf-8"),
        data_type="USERINFO",
    )
    users, stats = adms_parser.parse_userinfo(text, device.serial_number)
    await device_user_svc.sync_from_device(session, device=device, users=users)
    payload.processing_status = "processed" if not stats.skipped else "partial"
    payload.processed_at = _utcnow()
    return wire_ok()


async def _handle_options(
    session: AsyncSession, device: Device, request: Request, body: bytes, text: str
) -> str:
    """Accept Security PUSH device parameters posted as ``table=options``."""
    payload = await _store_payload(
        session,
        device=device,
        endpoint="cdata",
        request=request,
        body=body,
        data_type="OPTIONS",
    )
    info = adms_parser.parse_registry_body(text)
    device_svc.merge_options(device, info)
    payload.processing_status = "processed"
    payload.processed_at = _utcnow()
    return wire_ok()


async def _handle_info_or_commands(
    session: AsyncSession, device: Device, request: Request, text: str
) -> str:
    if request.method == "POST" and text.strip():
        payload = await _store_payload(
            session,
            device=device,
            endpoint="cdata",
            request=request,
            body=text.encode("utf-8"),
            data_type="INFO",
        )
        info = adms_parser.parse_device_info(text)
        device_svc.merge_options(device, info)
        device.last_device_info = info
        payload.processing_status = "processed"
        payload.processed_at = _utcnow()
        await event_svc.emit(
            session, device_id=device.id, event_type="device_info_received", payload=info
        )
    return await _drain_wire(session, device)


# ---------------------------------------------------------------------------
# /iclock/registry
# ---------------------------------------------------------------------------


@router.api_route("/registry", methods=["GET", "POST"])
async def handle_registry(
    request: Request, session: AsyncSession = Depends(get_db)
) -> PlainTextResponse:
    sn = _sn_or_error(request)
    if isinstance(sn, PlainTextResponse):
        return sn
    if not await check_adms_limit(request, serial=sn, endpoint="registry"):
        return PlainTextResponse("Rate limit exceeded", status_code=429)
    body = await request.body()
    if _body_too_large(request, body):
        return PlainTextResponse("Request body too large", status_code=413)

    device = await _require_device(session, serial=sn)
    if isinstance(device, PlainTextResponse):
        await session.rollback()
        return device

    text = body.decode("utf-8", errors="replace")
    try:
        re_registered = device.last_registry_at is not None
        device.last_registry_at = _utcnow()
        info: dict[str, str] = {}
        if text.strip():
            payload = await _store_payload(
                session,
                device=device,
                endpoint="registry",
                request=request,
                body=body,
            )
            info = adms_parser.parse_registry_body(text)
            device_svc.merge_options(device, info)
            device.last_registry_payload = info
            payload.processing_status = "processed"
            payload.processed_at = _utcnow()
            await event_svc.emit(
                session,
                device_id=device.id,
                event_type="device_re_registered" if re_registered else "device_registered",
                payload=info,
            )
        is_security_push = info.get("DeviceType", "").lower() == "acc" or (
            (device.options or {}).get("DeviceType", "").lower() == "acc"
        )
        if is_security_push:
            device.adms_registry_code = _new_push_identifier()
            device.adms_session_id = _new_push_identifier()
            device.push_protocol = request.query_params.get("pushver") or info.get("PushVersion")
        await session.commit()
    except Exception as exc:
        # M-04: registry state may not have been stored — 500/"ERROR" so the
        # device retries instead of assuming registration succeeded.
        await session.rollback()
        log.error("registry_error", serial=sn, error=str(exc))
        return PlainTextResponse("ERROR", status_code=500)
    if device.adms_registry_code:
        return PlainTextResponse(
            wire_registry_code(device.adms_registry_code),
            status_code=200,
            headers={"Set-Cookie": f"JSESSIONID={device.adms_session_id}; Path=/; HttpOnly"},
        )
    return PlainTextResponse(wire_ok(), status_code=200)


# ---------------------------------------------------------------------------
# /iclock/push — Security PUSH configuration after ACC registration
# ---------------------------------------------------------------------------


@router.api_route("/push", methods=["GET", "POST"])
async def handle_push(
    request: Request, session: AsyncSession = Depends(get_db)
) -> PlainTextResponse:
    sn = _sn_or_error(request)
    if isinstance(sn, PlainTextResponse):
        return sn
    if not await check_adms_limit(request, serial=sn, endpoint="push"):
        return PlainTextResponse("Rate limit exceeded", status_code=429)
    body = await request.body()
    if _body_too_large(request, body):
        return PlainTextResponse("Request body too large", status_code=413)

    device = await _require_device(session, serial=sn)
    if isinstance(device, PlainTextResponse):
        await session.rollback()
        return device
    if not device.adms_registry_code:
        # A panel must complete /registry before it can establish a PUSH
        # session. Returning OK makes it retry registration without exposing
        # configuration to an unknown device.
        await session.commit()
        return PlainTextResponse(wire_ok(), status_code=200)
    try:
        device.last_cdata_at = _utcnow()
        response_text = wire_security_push_config(**_security_push_kwargs(device))
        await session.commit()
    except Exception as exc:
        await session.rollback()
        log.error("push_error", serial=sn, error=str(exc))
        return PlainTextResponse("ERROR", status_code=500)
    return PlainTextResponse(response_text, status_code=200)


# ---------------------------------------------------------------------------
# /iclock/getrequest
# ---------------------------------------------------------------------------


@router.get("/getrequest")
async def handle_getrequest(
    request: Request, session: AsyncSession = Depends(get_db)
) -> PlainTextResponse:
    sn = _sn_or_error(request)
    if isinstance(sn, PlainTextResponse):
        return sn
    if not await check_adms_limit(request, serial=sn, endpoint="getrequest"):
        return PlainTextResponse("Rate limit exceeded", status_code=429)
    body = await request.body()
    if _body_too_large(request, body):
        return PlainTextResponse("Request body too large", status_code=413)

    device = await _require_device(session, serial=sn)
    if isinstance(device, PlainTextResponse):
        await session.rollback()
        return device
    try:
        response_text = await _drain_wire(session, device)
        device.last_command_poll_at = _utcnow()
        await session.commit()
    except Exception as exc:
        # M-04: drain failures leave commands `pending`, so answering OK is
        # safe — the device will simply poll again. Nothing is lost.
        await session.rollback()
        log.error("getrequest_error", serial=sn, error=str(exc))
        return PlainTextResponse(wire_ok(), status_code=200)
    return PlainTextResponse(response_text, status_code=200)


# ---------------------------------------------------------------------------
# /iclock/devicecmd
# ---------------------------------------------------------------------------


@router.post("/devicecmd")
async def handle_devicecmd(
    request: Request, session: AsyncSession = Depends(get_db)
) -> PlainTextResponse:
    sn = _sn_or_error(request)
    if isinstance(sn, PlainTextResponse):
        return sn
    if not await check_adms_limit(request, serial=sn, endpoint="devicecmd"):
        return PlainTextResponse("Rate limit exceeded", status_code=429)
    body = await request.body()
    if _body_too_large(request, body):
        return PlainTextResponse("Request body too large", status_code=413)

    device = await _require_device(session, serial=sn)
    if isinstance(device, PlainTextResponse):
        await session.rollback()
        return device

    text = body.decode("utf-8", errors="replace")
    try:
        payload = await _store_payload(
            session,
            device=device,
            endpoint="devicecmd",
            request=request,
            body=body,
        )
        results = adms_parser.parse_command_results(text, sn)
        for result in results:
            log.info(
                "command_result",
                serial=sn,
                protocol_id=result.protocol_command_id,
                return_code=result.return_code,
            )
            await command_svc.confirm_result(
                session, device=device, result=result, response=text[:2000]
            )
        payload.processing_status = "processed"
        payload.processed_at = _utcnow()
        device.last_command_result_at = _utcnow()
        await session.commit()
    except Exception as exc:
        # M-04: the device already executed the command; confirmations are
        # idempotent (see confirm_result), so OK + device retry is safe.
        await session.rollback()
        log.error("devicecmd_error", serial=sn, error=str(exc))
        return PlainTextResponse("OK", status_code=200)
    return PlainTextResponse(wire_ok(), status_code=200)


# ---------------------------------------------------------------------------
# /iclock/inspect (opt-in debug, disabled by default §26)
# ---------------------------------------------------------------------------


@router.get("/inspect")
async def handle_inspect(session: AsyncSession = Depends(get_db)) -> JSONResponse:
    if not get_settings().zkteco_enable_inspect:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    from sqlalchemy import func, select

    from app.models.device import Device
    from app.services import device as device_svc

    result = await session.execute(select(Device).order_by(Device.serial_number).limit(1000))
    devices = [
        {
            "serial": d.serial_number,
            "name": d.name,
            "firmware": d.firmware_version,
            "derived_status": device_svc.derived_status(d),
            "timezone": d.timezone,
            "last_activity": d.last_activity_at.isoformat() if d.last_activity_at else None,
            "option_keys": sorted((d.options or {}).keys()),
        }
        for d in result.scalars().all()
    ]
    total = await session.scalar(select(func.count()).select_from(Device)) or 0
    return JSONResponse(
        {"count": total, "time": _utcnow().isoformat(), "devices": devices}, status_code=200
    )

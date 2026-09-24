"""Corporate, people and employment administration endpoints."""

from __future__ import annotations

import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from json import JSONDecodeError, dumps, loads
from secrets import randbelow, token_urlsafe
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from redis.exceptions import RedisError
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.api.v1 import deps
from app.api.v1.schemas import (
    AttendanceOut,
    BusinessAddress,
    CompanyIn,
    CompanyOut,
    CompanyPatch,
    CorporateGroupIn,
    CorporateGroupOut,
    EmploymentCompensationIn,
    EmploymentCompensationOut,
    EmploymentIn,
    EmploymentOut,
    EnrollmentCandidateOut,
    EnrollmentRequestIn,
    EnrollmentRequestOut,
    EnrollmentRequestStatusIn,
    HardDeleteCaptchaOut,
    HardDeleteIn,
    HolidayGenerationOut,
    HolidayIn,
    HolidayOut,
    PersonAttendancePageOut,
    PersonIn,
    PersonOut,
    PersonPatch,
    PersonPhotoOut,
    PersonSensitiveIdentifiersIn,
    PersonSensitiveIdentifiersOut,
    ScheduleAssignmentIn,
    ScheduleAssignmentOut,
    ScheduleSlotIn,
    ScheduleSlotOut,
    SiteIn,
    SiteOut,
    SitePatch,
    WorkScheduleIn,
    WorkScheduleOut,
    WorkSchedulePatch,
)
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.device import AttendanceLog, Device, DeviceUser
from app.models.hr import (
    Address,
    Company,
    CorporateGroup,
    Employment,
    EmploymentCompensation,
    EnrollmentRequest,
    Holiday,
    Person,
    PersonPhoto,
    PersonSensitiveIdentifier,
    ScheduleAssignment,
    ScheduleSlot,
    Site,
    WorkSchedule,
)
from app.models.user import User
from app.services import access as access_svc
from app.services import audit as audit_svc
from app.services.holidays import ensure_statutory_holidays
from app.services.hr_pii import (
    PiiEncryptionUnavailableError,
    decrypt_identifier,
    encrypt_identifier,
)


def _validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid timezone: {value}") from exc


async def _audit(
    session: AsyncSession,
    user: User,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    rid: str,
) -> None:
    await audit_svc.record(
        session,
        action=action,
        user_id=user.id,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=rid,
    )


groups_router = APIRouter(prefix="/corporate-groups", tags=["corporate-groups"])


@groups_router.get("", response_model=list[CorporateGroupOut])
async def list_groups(
    user: User = Depends(deps.require_permission("companies.read")),
    session: AsyncSession = Depends(get_db),
) -> list[CorporateGroup]:
    allowed = await access_svc.group_ids(session, user)
    result = await session.execute(
        select(CorporateGroup).where(CorporateGroup.id.in_(allowed)).order_by(CorporateGroup.name)
    )
    return list(result.scalars())


@groups_router.post("", response_model=CorporateGroupOut, status_code=201)
async def create_group(
    payload: CorporateGroupIn,
    user: User = Depends(deps.require_permission("companies.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> CorporateGroup:
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Only a superuser can create corporate groups")
    if await session.scalar(select(CorporateGroup).where(CorporateGroup.code == payload.code)):
        raise HTTPException(status_code=409, detail="Corporate group code already exists")
    row = CorporateGroup(**payload.model_dump())
    session.add(row)
    await session.flush()
    await _audit(session, user, "corporate_group.create", "corporate_group", row.id, rid)
    await session.commit()
    return row


companies_router = APIRouter(prefix="/companies", tags=["companies"])

HARD_DELETE_CAPTCHA_TTL_SECONDS = 300
_UNSET = object()


async def _replace_business_address(owner: Company | Site, payload: BusinessAddress | None) -> None:
    """Replace the single structured address owned by a company or branch."""

    if payload is None:
        owner.address = None
        return
    values = payload.model_dump()
    if owner.address is None:
        owner.address = Address(**values)
        return
    for key, value in values.items():
        setattr(owner.address, key, value)


async def _require_hard_delete_captcha(
    user: User, resource: str, resource_id: uuid.UUID, payload: HardDeleteIn
) -> None:
    if not user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Only a superuser can permanently delete records"
        )
    key = f"hard-delete:{user.id}:{resource}:{resource_id}:{payload.captcha_token}"
    try:
        expected = await get_redis().getdel(key)
    except RedisError as exc:
        raise HTTPException(
            status_code=503, detail="Deletion confirmation service unavailable"
        ) from exc
    if expected is None or not compare_digest(expected, payload.captcha_answer):
        raise HTTPException(status_code=422, detail="Deletion CAPTCHA is invalid or expired")


async def _new_hard_delete_captcha(
    user: User, resource: str, resource_id: uuid.UUID
) -> HardDeleteCaptchaOut:
    if not user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Only a superuser can permanently delete records"
        )
    token = token_urlsafe(24)
    answer = f"{randbelow(1_000_000):06d}"
    key = f"hard-delete:{user.id}:{resource}:{resource_id}:{token}"
    try:
        await get_redis().setex(key, HARD_DELETE_CAPTCHA_TTL_SECONDS, answer)
    except RedisError as exc:
        raise HTTPException(
            status_code=503, detail="Deletion confirmation service unavailable"
        ) from exc
    return HardDeleteCaptchaOut(
        token=token,
        prompt=f"Escribe el código {answer} para confirmar la eliminación definitiva.",
        expires_in_seconds=HARD_DELETE_CAPTCHA_TTL_SECONDS,
    )


@companies_router.get("", response_model=list[CompanyOut])
async def list_companies(
    corporate_group_id: uuid.UUID | None = None,
    include_inactive: bool = False,
    user: User = Depends(deps.require_permission("companies.read")),
    session: AsyncSession = Depends(get_db),
) -> list[Company]:
    query = select(Company).options(selectinload(Company.address)).order_by(Company.legal_name)
    query = query.where(Company.id.in_(await access_svc.company_ids(session, user)))
    if not include_inactive:
        query = query.where(Company.active.is_(True))
    if corporate_group_id:
        query = query.where(Company.corporate_group_id == corporate_group_id)
    return list((await session.execute(query)).scalars())


@companies_router.post("", response_model=CompanyOut, status_code=201)
async def create_company(
    payload: CompanyIn,
    user: User = Depends(deps.require_permission("companies.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Company:
    _validate_timezone(payload.timezone)
    await access_svc.require_group_management(session, user, payload.corporate_group_id)
    values = payload.model_dump(exclude={"address"})
    row = Company(**values)
    session.add(row)
    await _replace_business_address(row, payload.address)
    await session.flush()
    await _audit(session, user, "company.create", "company", row.id, rid)
    await session.commit()
    return row


@companies_router.patch("/{company_id}", response_model=CompanyOut)
async def update_company(
    company_id: uuid.UUID,
    payload: CompanyPatch,
    user: User = Depends(deps.require_permission("companies.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Company:
    await access_svc.require_company(session, user, company_id)
    row = await session.scalar(
        select(Company).options(selectinload(Company.address)).where(Company.id == company_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Company not found")
    changes = payload.model_dump(exclude_unset=True)
    address = payload.address if "address" in payload.model_fields_set else _UNSET
    changes.pop("address", None)
    if "timezone" in changes and changes["timezone"] is not None:
        _validate_timezone(changes["timezone"])
    for key, value in changes.items():
        setattr(row, key, value)
    if address is not _UNSET:
        await _replace_business_address(row, payload.address)
    await session.flush()
    await _audit(session, user, "company.update", "company", row.id, rid)
    await session.commit()
    return row


@companies_router.delete("/{company_id}", status_code=204)
async def soft_delete_company(
    company_id: uuid.UUID,
    user: User = Depends(deps.require_permission("companies.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> None:
    row = await access_svc.require_company(session, user, company_id)
    has_active_branches = await session.scalar(
        select(Site.id).where(Site.company_id == company_id, Site.active.is_(True))
    )
    if has_active_branches:
        raise HTTPException(
            status_code=409, detail="Soft-delete every active branch before deleting company"
        )
    row.active = False
    await session.flush()
    await _audit(session, user, "company.soft_delete", "company", row.id, rid)
    await session.commit()


@companies_router.post("/{company_id}/hard-delete-captcha", response_model=HardDeleteCaptchaOut)
async def company_hard_delete_captcha(
    company_id: uuid.UUID,
    user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_db),
) -> HardDeleteCaptchaOut:
    row = await access_svc.require_company(session, user, company_id)
    if row.active:
        raise HTTPException(status_code=409, detail="Soft-delete company before permanent deletion")
    return await _new_hard_delete_captcha(user, "company", company_id)


@companies_router.delete("/{company_id}/hard", status_code=204)
async def hard_delete_company(
    company_id: uuid.UUID,
    payload: HardDeleteIn,
    user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> None:
    row = await access_svc.require_company(session, user, company_id)
    if row.active:
        raise HTTPException(status_code=409, detail="Soft-delete company before permanent deletion")
    await _require_hard_delete_captcha(user, "company", company_id, payload)
    if await session.scalar(select(Site.id).where(Site.company_id == company_id)):
        raise HTTPException(
            status_code=409, detail="Permanently delete all branches before deleting company"
        )
    company_dependencies = (
        (Employment, "employments"),
        (WorkSchedule, "work schedules"),
        (Holiday, "holidays"),
    )
    for model, label in company_dependencies:
        if await session.scalar(select(model.id).where(model.company_id == company_id)):
            raise HTTPException(status_code=409, detail=f"Company still has {label}")
    await session.delete(row)
    await session.flush()
    await _audit(session, user, "company.hard_delete", "company", company_id, rid)
    await session.commit()


sites_router = APIRouter(prefix="/sites", tags=["sites"])


@sites_router.get("", response_model=list[SiteOut])
async def list_sites(
    company_id: uuid.UUID | None = None,
    include_inactive: bool = False,
    user: User = Depends(deps.require_permission("sites.read")),
    session: AsyncSession = Depends(get_db),
) -> list[Site]:
    query = select(Site).options(selectinload(Site.address)).order_by(Site.name)
    query = query.where(Site.company_id.in_(await access_svc.company_ids(session, user)))
    if not include_inactive:
        query = query.where(Site.active.is_(True))
    if company_id:
        query = query.where(Site.company_id == company_id)
    return list((await session.execute(query)).scalars())


@sites_router.post("", response_model=SiteOut, status_code=201)
async def create_site(
    payload: SiteIn,
    user: User = Depends(deps.require_permission("sites.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Site:
    _validate_timezone(payload.timezone)
    company = await access_svc.require_company(session, user, payload.company_id)
    if not company.active:
        raise HTTPException(status_code=409, detail="Cannot add a branch to a soft-deleted company")
    values = payload.model_dump(exclude={"address"})
    row = Site(**values)
    session.add(row)
    await _replace_business_address(row, payload.address)
    await session.flush()
    await _audit(session, user, "site.create", "site", row.id, rid)
    await session.commit()
    return row


@sites_router.patch("/{site_id}", response_model=SiteOut)
async def update_site(
    site_id: uuid.UUID,
    payload: SitePatch,
    user: User = Depends(deps.require_permission("sites.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Site:
    await access_svc.require_site(session, user, site_id)
    row = await session.scalar(
        select(Site).options(selectinload(Site.address)).where(Site.id == site_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    changes = payload.model_dump(exclude_unset=True)
    address = payload.address if "address" in payload.model_fields_set else _UNSET
    changes.pop("address", None)
    if "timezone" in changes and changes["timezone"] is not None:
        _validate_timezone(changes["timezone"])
    for key, value in changes.items():
        setattr(row, key, value)
    if address is not _UNSET:
        await _replace_business_address(row, payload.address)
    await session.flush()
    await _audit(session, user, "site.update", "site", row.id, rid)
    await session.commit()
    return row


@sites_router.delete("/{site_id}", status_code=204)
async def soft_delete_site(
    site_id: uuid.UUID,
    user: User = Depends(deps.require_permission("sites.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> None:
    row = await access_svc.require_site(session, user, site_id)
    row.active = False
    await session.flush()
    await _audit(session, user, "site.soft_delete", "site", row.id, rid)
    await session.commit()


@sites_router.post("/{site_id}/hard-delete-captcha", response_model=HardDeleteCaptchaOut)
async def site_hard_delete_captcha(
    site_id: uuid.UUID,
    user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_db),
) -> HardDeleteCaptchaOut:
    row = await access_svc.require_site(session, user, site_id)
    if row.active:
        raise HTTPException(status_code=409, detail="Soft-delete branch before permanent deletion")
    return await _new_hard_delete_captcha(user, "site", site_id)


@sites_router.delete("/{site_id}/hard", status_code=204)
async def hard_delete_site(
    site_id: uuid.UUID,
    payload: HardDeleteIn,
    user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> None:
    row = await access_svc.require_site(session, user, site_id)
    if row.active:
        raise HTTPException(status_code=409, detail="Soft-delete branch before permanent deletion")
    await _require_hard_delete_captcha(user, "site", site_id, payload)
    if await session.scalar(select(Device.id).where(Device.site_id == site_id)):
        raise HTTPException(status_code=409, detail="Branch still has assigned devices")
    await session.delete(row)
    await session.flush()
    await _audit(session, user, "site.hard_delete", "site", site_id, rid)
    await session.commit()


people_router = APIRouter(prefix="/people", tags=["people"])

MAX_PERSON_PHOTO_BYTES = 5 * 1024 * 1024
PERSON_PHOTO_TYPES = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}


def _photo_content_type(data: bytes, claimed_type: str | None) -> str:
    """Accept only browser-safe raster formats and verify their signatures."""

    if claimed_type in PERSON_PHOTO_TYPES and data.startswith(PERSON_PHOTO_TYPES[claimed_type]):
        return claimed_type
    if claimed_type == "image/webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return claimed_type
    raise HTTPException(status_code=422, detail="Photo must be a PNG, JPEG, or WebP image")


def _attendance_cursor(row: AttendanceLog) -> str:
    payload = dumps({"recorded_at": row.recorded_at.isoformat(), "id": str(row.id)})
    return urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _parse_attendance_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = loads(urlsafe_b64decode(padded.encode()).decode())
        recorded_at = datetime.fromisoformat(value["recorded_at"])
        row_id = uuid.UUID(value["id"])
    except (KeyError, TypeError, ValueError, JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid attendance cursor") from exc
    if recorded_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="Invalid attendance cursor")
    return recorded_at, row_id


@people_router.get("", response_model=list[PersonOut])
async def list_people(
    corporate_group_id: uuid.UUID,
    limit: int = Query(default=50, le=200),
    user: User = Depends(deps.require_permission("people.read")),
    session: AsyncSession = Depends(get_db),
) -> list[Person]:
    await access_svc.require_group(session, user, corporate_group_id)
    query = (
        select(Person)
        .where(
            Person.corporate_group_id == corporate_group_id,
            Person.id.in_(await access_svc.person_ids(session, user)),
        )
        .order_by(Person.last_name, Person.first_name)
        .limit(limit)
    )
    return list((await session.execute(query)).scalars())


@people_router.post("", response_model=PersonOut, status_code=201)
async def create_person(
    payload: PersonIn,
    user: User = Depends(deps.require_permission("people.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Person:
    # Creating a group-level identity requires a whole-group scope. A
    # company-only operator may manage people already employed by that
    # company, but cannot create identities that initially have no owner.
    await access_svc.require_group_management(session, user, payload.corporate_group_id)
    row = Person(**payload.model_dump())
    session.add(row)
    await session.flush()
    await _audit(session, user, "person.create", "person", row.id, rid)
    await session.commit()
    return row


@people_router.get("/{person_id}", response_model=PersonOut)
async def get_person(
    person_id: uuid.UUID,
    user: User = Depends(deps.require_permission("people.read")),
    session: AsyncSession = Depends(get_db),
) -> Person:
    return await access_svc.require_person(session, user, person_id)


@people_router.patch("/{person_id}", response_model=PersonOut)
async def update_person(
    person_id: uuid.UUID,
    payload: PersonPatch,
    user: User = Depends(deps.require_permission("people.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Person:
    row = await access_svc.require_person(session, user, person_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return row
    for key, value in changes.items():
        setattr(row, key, value)
    await session.flush()
    await _audit(session, user, "person.update", "person", row.id, rid)
    await session.commit()
    return row


@people_router.get("/{person_id}/photo")
async def get_person_photo(
    person_id: uuid.UUID,
    user: User = Depends(deps.require_permission("people.read")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Response:
    await access_svc.require_person(session, user, person_id)
    row = await session.scalar(select(PersonPhoto).where(PersonPhoto.person_id == person_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Worker photo not found")
    await _audit(session, user, "person.photo.read", "person", person_id, rid)
    await session.commit()
    return Response(
        content=row.image_data,
        media_type=row.content_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": 'inline; filename="worker-photo"',
        },
    )


@people_router.put("/{person_id}/photo", response_model=PersonPhotoOut)
async def update_person_photo(
    person_id: uuid.UUID,
    photo: UploadFile = File(...),
    user: User = Depends(deps.require_permission("people.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> PersonPhoto:
    await access_svc.require_person(session, user, person_id)
    if photo.size is not None and photo.size > MAX_PERSON_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Photo must not exceed 5 MB")
    image_data = await photo.read(MAX_PERSON_PHOTO_BYTES + 1)
    if not image_data:
        raise HTTPException(status_code=422, detail="Photo is empty")
    if len(image_data) > MAX_PERSON_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Photo must not exceed 5 MB")
    content_type = _photo_content_type(image_data, photo.content_type)
    row = await session.scalar(select(PersonPhoto).where(PersonPhoto.person_id == person_id))
    if row is None:
        row = PersonPhoto(
            person_id=person_id,
            image_data=image_data,
            content_type=content_type,
            size_bytes=len(image_data),
            sha256=sha256(image_data).hexdigest(),
        )
        session.add(row)
    else:
        row.image_data = image_data
        row.content_type = content_type
        row.size_bytes = len(image_data)
        row.sha256 = sha256(image_data).hexdigest()
    await session.flush()
    await _audit(session, user, "person.photo.update", "person", person_id, rid)
    await session.commit()
    return row


@people_router.delete("/{person_id}/photo", status_code=204)
async def delete_person_photo(
    person_id: uuid.UUID,
    user: User = Depends(deps.require_permission("people.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> None:
    await access_svc.require_person(session, user, person_id)
    row = await session.scalar(select(PersonPhoto).where(PersonPhoto.person_id == person_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Worker photo not found")
    await session.delete(row)
    await session.flush()
    await _audit(session, user, "person.photo.delete", "person", person_id, rid)
    await session.commit()


def _pii_unavailable(exc: PiiEncryptionUnavailableError) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="HR sensitive identifiers are unavailable: configure ZKTECO_HR_PII_ENCRYPTION_KEY",
    )


@people_router.get("/{person_id}/sensitive", response_model=PersonSensitiveIdentifiersOut)
async def get_person_sensitive_identifiers(
    person_id: uuid.UUID,
    user: User = Depends(deps.require_permission("people.sensitive.read")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> PersonSensitiveIdentifiersOut:
    await access_svc.require_person(session, user, person_id)
    row = await session.scalar(
        select(PersonSensitiveIdentifier).where(PersonSensitiveIdentifier.person_id == person_id)
    )
    if row is None:
        await _audit(session, user, "person.sensitive_identifiers.read", "person", person_id, rid)
        await session.commit()
        return PersonSensitiveIdentifiersOut()
    try:
        result = PersonSensitiveIdentifiersOut(
            curp=decrypt_identifier(row.curp_encrypted) if row.curp_encrypted else None,
            rfc=decrypt_identifier(row.rfc_encrypted) if row.rfc_encrypted else None,
            nss=decrypt_identifier(row.nss_encrypted) if row.nss_encrypted else None,
            fiscal_name=decrypt_identifier(row.fiscal_name_encrypted)
            if row.fiscal_name_encrypted
            else None,
            tax_regime=decrypt_identifier(row.tax_regime_encrypted)
            if row.tax_regime_encrypted
            else None,
            fiscal_postal_code=decrypt_identifier(row.fiscal_postal_code_encrypted)
            if row.fiscal_postal_code_encrypted
            else None,
        )
        await _audit(session, user, "person.sensitive_identifiers.read", "person", person_id, rid)
        await session.commit()
        return result
    except PiiEncryptionUnavailableError as exc:
        raise _pii_unavailable(exc) from exc


@people_router.put("/{person_id}/sensitive", response_model=PersonSensitiveIdentifiersOut)
async def update_person_sensitive_identifiers(
    person_id: uuid.UUID,
    payload: PersonSensitiveIdentifiersIn,
    user: User = Depends(deps.require_permission("people.sensitive.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> PersonSensitiveIdentifiersOut:
    await access_svc.require_person(session, user, person_id)
    try:
        row = await session.scalar(
            select(PersonSensitiveIdentifier).where(
                PersonSensitiveIdentifier.person_id == person_id
            )
        )
        if row is None:
            row = PersonSensitiveIdentifier(person_id=person_id)
            session.add(row)
        for field in ("curp", "rfc", "nss"):
            if field not in payload.model_fields_set:
                continue
            value = getattr(payload, field)
            encrypted_field = f"{field}_encrypted"
            hash_field = f"{field}_hash"
            if value is None:
                setattr(row, encrypted_field, None)
                setattr(row, hash_field, None)
            else:
                encrypted, digest = encrypt_identifier(value)
                setattr(row, encrypted_field, encrypted)
                setattr(row, hash_field, digest)
        for field in ("fiscal_name", "tax_regime", "fiscal_postal_code"):
            if field not in payload.model_fields_set:
                continue
            value = getattr(payload, field)
            encrypted_field = f"{field}_encrypted"
            encrypted_value = encrypt_identifier(value)[0] if value is not None else None
            setattr(row, encrypted_field, encrypted_value)
        await session.flush()
        await _audit(session, user, "person.sensitive_identifiers.update", "person", person_id, rid)
        await session.commit()
        return PersonSensitiveIdentifiersOut(
            curp=decrypt_identifier(row.curp_encrypted) if row.curp_encrypted else None,
            rfc=decrypt_identifier(row.rfc_encrypted) if row.rfc_encrypted else None,
            nss=decrypt_identifier(row.nss_encrypted) if row.nss_encrypted else None,
            fiscal_name=decrypt_identifier(row.fiscal_name_encrypted)
            if row.fiscal_name_encrypted
            else None,
            tax_regime=decrypt_identifier(row.tax_regime_encrypted)
            if row.tax_regime_encrypted
            else None,
            fiscal_postal_code=decrypt_identifier(row.fiscal_postal_code_encrypted)
            if row.fiscal_postal_code_encrypted
            else None,
        )
    except PiiEncryptionUnavailableError as exc:
        raise _pii_unavailable(exc) from exc


@people_router.get("/{person_id}/attendance", response_model=PersonAttendancePageOut)
async def list_person_attendance(
    person_id: uuid.UUID,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=100),
    user: User = Depends(deps.require_permission("attendance.read")),
    session: AsyncSession = Depends(get_db),
) -> PersonAttendancePageOut:
    """List captured marks, newest first, without offset pagination drift.

    A check-in belongs to a person only after a device identity is linked to
    that person.  This intentionally exposes the raw device record; schedule
    interpretation is a separate payroll/attendance-calculation concern.
    """
    await access_svc.require_person(session, user, person_id)
    for label, value in (("date_from", date_from), ("date_to", date_to)):
        if value is not None and value.tzinfo is None:
            raise HTTPException(status_code=422, detail=f"{label} must include a timezone")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be <= date_to")
    if date_from is None:
        date_from = datetime.now(UTC) - timedelta(days=30)

    query = (
        select(AttendanceLog)
        .join(DeviceUser, AttendanceLog.device_user_id == DeviceUser.id)
        .where(
            DeviceUser.person_id == person_id,
            AttendanceLog.device_id.in_(await access_svc.device_ids(session, user)),
            AttendanceLog.recorded_at >= date_from,
        )
        .order_by(AttendanceLog.recorded_at.desc(), AttendanceLog.id.desc())
        .limit(limit + 1)
    )
    if date_to is not None:
        query = query.where(AttendanceLog.recorded_at <= date_to)
    if cursor is not None:
        cursor_at, cursor_id = _parse_attendance_cursor(cursor)
        query = query.where(
            or_(
                AttendanceLog.recorded_at < cursor_at,
                and_(AttendanceLog.recorded_at == cursor_at, AttendanceLog.id < cursor_id),
            )
        )
    rows = list((await session.execute(query)).scalars())
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    return PersonAttendancePageOut(
        items=[
            AttendanceOut(
                id=row.id,
                device_id=row.device_id,
                device_user_pin=row.device_user_pin,
                recorded_at=row.recorded_at,
                status=row.status,
                verify_mode=row.verify_mode,
                work_code=row.work_code,
            )
            for row in page_rows
        ],
        next_cursor=_attendance_cursor(page_rows[-1]) if has_more and page_rows else None,
    )


employments_router = APIRouter(prefix="/employments", tags=["employments"])


@employments_router.get("", response_model=list[EmploymentOut])
async def list_employments(
    company_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    user: User = Depends(deps.require_permission("employments.read")),
    session: AsyncSession = Depends(get_db),
) -> list[Employment]:
    query = (
        select(Employment)
        .where(Employment.company_id.in_(await access_svc.company_ids(session, user)))
        .order_by(Employment.employee_number)
    )
    if company_id:
        await access_svc.require_company(session, user, company_id)
        query = query.where(Employment.company_id == company_id)
    if person_id:
        await access_svc.require_person(session, user, person_id)
        query = query.where(Employment.person_id == person_id)
    return list((await session.execute(query)).scalars())


@people_router.post("/{person_id}/employments", response_model=EmploymentOut, status_code=201)
async def create_employment(
    person_id: uuid.UUID,
    payload: EmploymentIn,
    user: User = Depends(deps.require_permission("employments.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Employment:
    person = await access_svc.require_person(session, user, person_id)
    company = await access_svc.require_company(session, user, payload.company_id)
    if person.corporate_group_id != company.corporate_group_id:
        raise HTTPException(status_code=422, detail="Person and company belong to different groups")
    if payload.site_id is not None:
        site = await access_svc.require_site(session, user, payload.site_id)
        if site.company_id != company.id:
            raise HTTPException(status_code=422, detail="Site belongs to another company")
    if payload.ended_on is not None and payload.ended_on < payload.started_on:
        raise HTTPException(status_code=422, detail="ended_on must not precede started_on")
    if payload.probation_ends_on is not None and payload.probation_ends_on < payload.started_on:
        raise HTTPException(status_code=422, detail="probation_ends_on must not precede started_on")
    row = Employment(person_id=person_id, **payload.model_dump())
    session.add(row)
    await session.flush()
    await _audit(session, user, "employment.create", "employment", row.id, rid)
    await session.commit()
    return row


@employments_router.put("/{employment_id}", response_model=EmploymentOut)
async def update_employment(
    employment_id: uuid.UUID,
    payload: EmploymentIn,
    user: User = Depends(deps.require_permission("employments.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Employment:
    row = await access_svc.require_employment(session, user, employment_id)
    if payload.company_id != row.company_id:
        raise HTTPException(status_code=422, detail="An employment cannot move to another company")
    if payload.site_id is not None:
        site = await access_svc.require_site(session, user, payload.site_id)
        if site.company_id != row.company_id:
            raise HTTPException(status_code=422, detail="Site belongs to another company")
    if payload.ended_on is not None and payload.ended_on < payload.started_on:
        raise HTTPException(status_code=422, detail="ended_on must not precede started_on")
    if payload.probation_ends_on is not None and payload.probation_ends_on < payload.started_on:
        raise HTTPException(status_code=422, detail="probation_ends_on must not precede started_on")
    first_schedule_date = await session.scalar(
        select(ScheduleAssignment.effective_from)
        .where(ScheduleAssignment.employment_id == row.id, ScheduleAssignment.active.is_(True))
        .order_by(ScheduleAssignment.effective_from)
        .limit(1)
    )
    if first_schedule_date is not None and payload.started_on > first_schedule_date:
        raise HTTPException(status_code=409, detail="Employment start would exclude schedule history")
    if payload.employee_number != row.employee_number:
        duplicate = await session.scalar(
            select(Employment.id).where(
                Employment.company_id == row.company_id,
                Employment.employee_number == payload.employee_number,
                Employment.id != row.id,
            )
        )
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="Employee number already exists in company")
    for key, value in payload.model_dump(exclude={"company_id"}).items():
        setattr(row, key, value)
    await _audit(session, user, "employment.update", "employment", row.id, rid)
    await session.commit()
    return row


def _compensation_out(row: EmploymentCompensation) -> EmploymentCompensationOut:
    try:
        return EmploymentCompensationOut(
            employment_id=row.employment_id,
            daily_salary=row.daily_salary,
            integrated_daily_salary=row.integrated_daily_salary,
            pay_frequency=row.pay_frequency,
            payment_method=row.payment_method,
            bank_clabe=decrypt_identifier(row.bank_clabe_encrypted)
            if row.bank_clabe_encrypted
            else None,
            imss_umf=row.imss_umf,
            imss_worker_type=row.imss_worker_type,
            imss_salary_type=row.imss_salary_type,
            imss_workday_type=row.imss_workday_type,
        )
    except PiiEncryptionUnavailableError as exc:
        raise _pii_unavailable(exc) from exc


@employments_router.get("/{employment_id}/compensation", response_model=EmploymentCompensationOut)
async def get_employment_compensation(
    employment_id: uuid.UUID,
    user: User = Depends(deps.require_permission("payroll.read")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> EmploymentCompensationOut:
    await access_svc.require_employment(session, user, employment_id)
    row = await session.scalar(
        select(EmploymentCompensation).where(EmploymentCompensation.employment_id == employment_id)
    )
    if row is None:
        await _audit(
            session, user, "employment.compensation.read", "employment", employment_id, rid
        )
        await session.commit()
        return EmploymentCompensationOut(employment_id=employment_id)
    result = _compensation_out(row)
    await _audit(session, user, "employment.compensation.read", "employment", employment_id, rid)
    await session.commit()
    return result


@employments_router.put("/{employment_id}/compensation", response_model=EmploymentCompensationOut)
async def update_employment_compensation(
    employment_id: uuid.UUID,
    payload: EmploymentCompensationIn,
    user: User = Depends(deps.require_permission("payroll.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> EmploymentCompensationOut:
    await access_svc.require_employment(session, user, employment_id)
    try:
        row = await session.scalar(
            select(EmploymentCompensation).where(
                EmploymentCompensation.employment_id == employment_id
            )
        )
        if row is None:
            row = EmploymentCompensation(employment_id=employment_id)
            session.add(row)
        values = payload.model_dump(exclude={"bank_clabe"})
        for key, value in values.items():
            setattr(row, key, value)
        if "bank_clabe" in payload.model_fields_set:
            row.bank_clabe_encrypted = (
                encrypt_identifier(payload.bank_clabe)[0] if payload.bank_clabe else None
            )
        await session.flush()
        await _audit(
            session, user, "employment.compensation.update", "employment", employment_id, rid
        )
        await session.commit()
        return _compensation_out(row)
    except PiiEncryptionUnavailableError as exc:
        raise _pii_unavailable(exc) from exc


schedules_router = APIRouter(prefix="/work-schedules", tags=["work-schedules"])


holidays_router = APIRouter(prefix="/holidays", tags=["holidays"])


@holidays_router.get("", response_model=list[HolidayOut])
async def list_holidays(
    company_id: uuid.UUID,
    year: int | None = Query(default=None, ge=2000, le=2200),
    user: User = Depends(deps.require_permission("schedules.read")),
    session: AsyncSession = Depends(get_db),
) -> list[Holiday]:
    await access_svc.require_company(session, user, company_id)
    query = select(Holiday).where(Holiday.company_id == company_id).order_by(Holiday.holiday_date)
    if year is not None:
        query = query.where(
            Holiday.holiday_date >= date(year, 1, 1), Holiday.holiday_date <= date(year, 12, 31)
        )
    return list((await session.execute(query)).scalars())


@holidays_router.post("", response_model=HolidayOut, status_code=201)
async def create_holiday(
    payload: HolidayIn,
    user: User = Depends(deps.require_permission("schedules.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> Holiday:
    await access_svc.require_company(session, user, payload.company_id)
    existing = await session.scalar(
        select(Holiday).where(
            Holiday.company_id == payload.company_id, Holiday.holiday_date == payload.holiday_date
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="A holiday already exists on this company date")
    row = Holiday(**payload.model_dump(), source="company", generated=False)
    session.add(row)
    await session.flush()
    await _audit(session, user, "holiday.create", "holiday", row.id, rid)
    await session.commit()
    return row


@companies_router.post("/{company_id}/holidays/generate", response_model=HolidayGenerationOut)
async def generate_holidays(
    company_id: uuid.UUID,
    year: int = Query(ge=2000, le=2200),
    user: User = Depends(deps.require_permission("schedules.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> HolidayGenerationOut:
    await access_svc.require_company(session, user, company_id)
    created, existing = await ensure_statutory_holidays(session, company_id, year)
    await session.flush()
    await _audit(session, user, "holiday.generate_statutory", "company", company_id, rid)
    await session.commit()
    return HolidayGenerationOut(
        year=year,
        created=created,
        existing=existing,
    )


def _schedule_out(row: WorkSchedule, slots: list[ScheduleSlot]) -> WorkScheduleOut:
    return WorkScheduleOut(
        id=row.id,
        company_id=row.company_id,
        name=row.name,
        timezone=row.timezone,
        automatic_exit_enabled=row.automatic_exit_enabled,
        version=row.version,
        active=row.active,
        slots=[ScheduleSlotOut.model_validate(slot) for slot in slots],
    )


@schedules_router.get("", response_model=list[WorkScheduleOut])
async def list_work_schedules(
    company_id: uuid.UUID | None = None,
    user: User = Depends(deps.require_permission("schedules.read")),
    session: AsyncSession = Depends(get_db),
) -> list[WorkScheduleOut]:
    query = (
        select(WorkSchedule)
        .where(WorkSchedule.company_id.in_(await access_svc.company_ids(session, user)))
        .order_by(WorkSchedule.name, WorkSchedule.version)
    )
    if company_id:
        await access_svc.require_company(session, user, company_id)
        query = query.where(WorkSchedule.company_id == company_id)
    schedules = list((await session.execute(query)).scalars())
    if not schedules:
        return []
    ids = [row.id for row in schedules]
    slots = list(
        (
            await session.execute(
                select(ScheduleSlot)
                .where(ScheduleSlot.work_schedule_id.in_(ids))
                .order_by(ScheduleSlot.day_of_week, ScheduleSlot.expected_at, ScheduleSlot.sequence)
            )
        ).scalars()
    )
    slots_by_schedule: dict[uuid.UUID, list[ScheduleSlot]] = {key: [] for key in ids}
    for slot in slots:
        slots_by_schedule[slot.work_schedule_id].append(slot)
    return [_schedule_out(row, slots_by_schedule[row.id]) for row in schedules]


@schedules_router.post("", response_model=WorkScheduleOut, status_code=201)
async def create_work_schedule(
    payload: WorkScheduleIn,
    user: User = Depends(deps.require_permission("schedules.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> WorkScheduleOut:
    _validate_timezone(payload.timezone)
    await access_svc.require_company(session, user, payload.company_id)
    positions = {(slot.day_of_week, slot.kind, slot.sequence) for slot in payload.slots}
    if len(positions) != len(payload.slots):
        raise HTTPException(status_code=422, detail="Duplicate schedule slot position")
    worked_days = {slot.day_of_week for slot in payload.slots}
    days_off = 7 - len(worked_days)
    if days_off not in (1, 2):
        raise HTTPException(
            status_code=422, detail="A schedule must define one or two weekly days off"
        )
    for day in worked_days:
        kinds = {slot.kind for slot in payload.slots if slot.day_of_week == day}
        if not {"entry", "exit"}.issubset(kinds):
            raise HTTPException(
                status_code=422, detail="Each working day requires entry and exit slots"
            )
    row = WorkSchedule(
        company_id=payload.company_id,
        name=payload.name,
        timezone=payload.timezone,
        automatic_exit_enabled=payload.automatic_exit_enabled,
    )
    session.add(row)
    await session.flush()
    slots = [ScheduleSlot(work_schedule_id=row.id, **slot.model_dump()) for slot in payload.slots]
    session.add_all(slots)
    await session.flush()
    await _audit(session, user, "work_schedule.create", "work_schedule", row.id, rid)
    await session.commit()
    return _schedule_out(row, slots)


def _validate_schedule_slots(slots: list[ScheduleSlotIn]) -> None:
    positions = {(slot.day_of_week, slot.kind, slot.sequence) for slot in slots}
    if len(positions) != len(slots):
        raise HTTPException(status_code=422, detail="Duplicate schedule slot position")
    worked_days = {slot.day_of_week for slot in slots}
    if 7 - len(worked_days) not in (1, 2):
        raise HTTPException(
            status_code=422, detail="A schedule must define one or two weekly days off"
        )
    for day in worked_days:
        kinds = {slot.kind for slot in slots if slot.day_of_week == day}
        if not {"entry", "exit"}.issubset(kinds):
            raise HTTPException(
                status_code=422, detail="Each working day requires entry and exit slots"
            )


@schedules_router.put("/{schedule_id}", response_model=WorkScheduleOut)
async def update_work_schedule(
    schedule_id: uuid.UUID,
    payload: WorkSchedulePatch,
    user: User = Depends(deps.require_permission("schedules.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> WorkScheduleOut:
    _validate_timezone(payload.timezone)
    _validate_schedule_slots(payload.slots)
    row = await session.get(WorkSchedule, schedule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Work schedule not found")
    await access_svc.require_company(session, user, row.company_id)
    assigned = await session.scalar(
        select(ScheduleAssignment.id)
        .where(ScheduleAssignment.work_schedule_id == schedule_id)
        .limit(1)
    )
    if assigned is not None:
        latest_version = await session.scalar(
            select(WorkSchedule.version)
            .where(WorkSchedule.company_id == row.company_id, WorkSchedule.name == payload.name)
            .order_by(WorkSchedule.version.desc())
            .limit(1)
        )
        row.active = False
        replacement = WorkSchedule(
            company_id=row.company_id,
            name=payload.name,
            timezone=payload.timezone,
            automatic_exit_enabled=payload.automatic_exit_enabled,
            version=(latest_version or 0) + 1,
        )
        session.add(replacement)
        await session.flush()
        slots = [
            ScheduleSlot(work_schedule_id=replacement.id, **slot.model_dump())
            for slot in payload.slots
        ]
        session.add_all(slots)
        await session.flush()
        await _audit(session, user, "work_schedule.version", "work_schedule", replacement.id, rid)
        await session.commit()
        return _schedule_out(replacement, slots)
    row.name = payload.name
    row.timezone = payload.timezone
    row.automatic_exit_enabled = payload.automatic_exit_enabled
    await session.execute(delete(ScheduleSlot).where(ScheduleSlot.work_schedule_id == row.id))
    slots = [ScheduleSlot(work_schedule_id=row.id, **slot.model_dump()) for slot in payload.slots]
    session.add_all(slots)
    await session.flush()
    await _audit(session, user, "work_schedule.update", "work_schedule", row.id, rid)
    await session.commit()
    return _schedule_out(row, slots)


@schedules_router.delete("/{schedule_id}", status_code=204)
async def delete_work_schedule(
    schedule_id: uuid.UUID,
    user: User = Depends(deps.require_permission("schedules.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> None:
    row = await session.get(WorkSchedule, schedule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Work schedule not found")
    await access_svc.require_company(session, user, row.company_id)
    if (
        await session.scalar(
            select(ScheduleAssignment.id)
            .where(ScheduleAssignment.work_schedule_id == schedule_id)
            .limit(1)
        )
        is not None
    ):
        raise HTTPException(
            status_code=409,
            detail="A schedule with assignment history cannot be deleted; edit creates a version",
        )
    await session.delete(row)
    await session.flush()
    await _audit(session, user, "work_schedule.delete", "work_schedule", schedule_id, rid)
    await session.commit()


@employments_router.post(
    "/{employment_id}/schedule-assignments", response_model=ScheduleAssignmentOut, status_code=201
)
async def assign_schedule(
    employment_id: uuid.UUID,
    payload: ScheduleAssignmentIn,
    user: User = Depends(deps.require_permission("schedules.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> ScheduleAssignment:
    employment = await access_svc.require_employment(session, user, employment_id)
    schedule = await session.get(WorkSchedule, payload.work_schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Employment or work schedule not found")
    await access_svc.require_company(session, user, schedule.company_id)
    if employment.company_id != schedule.company_id:
        raise HTTPException(status_code=422, detail="Schedule belongs to another company")
    if payload.effective_to is not None and payload.effective_to < payload.effective_from:
        raise HTTPException(status_code=422, detail="effective_to must not precede effective_from")
    conflicts = select(ScheduleAssignment).where(
        ScheduleAssignment.employment_id == employment_id,
        ScheduleAssignment.active.is_(True),
        ScheduleAssignment.effective_from <= (payload.effective_to or date.max),
        or_(
            ScheduleAssignment.effective_to.is_(None),
            ScheduleAssignment.effective_to >= payload.effective_from,
        ),
    )
    if await session.scalar(conflicts) is not None:
        raise HTTPException(
            status_code=409, detail="Schedule assignment overlaps an existing assignment"
        )
    row = ScheduleAssignment(employment_id=employment_id, **payload.model_dump())
    session.add(row)
    await session.flush()
    await _audit(session, user, "schedule_assignment.create", "schedule_assignment", row.id, rid)
    await session.commit()
    return row


@employments_router.put(
    "/{employment_id}/schedule-assignments/current", response_model=ScheduleAssignmentOut
)
async def replace_current_schedule(
    employment_id: uuid.UUID,
    payload: ScheduleAssignmentIn,
    user: User = Depends(deps.require_permission("schedules.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> ScheduleAssignment:
    employment = await access_svc.require_employment(session, user, employment_id)
    # Serialize changes for this employment before reading its assignment.
    await session.execute(select(Employment.id).where(Employment.id == employment_id).with_for_update())
    schedule = await session.get(WorkSchedule, payload.work_schedule_id)
    if schedule is None or not schedule.active:
        raise HTTPException(status_code=404, detail="Active work schedule not found")
    await access_svc.require_company(session, user, schedule.company_id)
    if schedule.company_id != employment.company_id:
        raise HTTPException(status_code=422, detail="Schedule belongs to another company")
    if payload.effective_to is not None:
        raise HTTPException(status_code=422, detail="Current schedule must remain open-ended")
    if payload.effective_from < employment.started_on or (
        employment.ended_on is not None and payload.effective_from > employment.ended_on
    ):
        raise HTTPException(status_code=422, detail="Schedule date is outside employment dates")

    current = await session.scalar(
        select(ScheduleAssignment)
        .where(
            ScheduleAssignment.employment_id == employment_id,
            ScheduleAssignment.active.is_(True),
            ScheduleAssignment.effective_to.is_(None),
        )
        .with_for_update()
    )
    if current is not None and payload.effective_from < current.effective_from:
        raise HTTPException(status_code=409, detail="New schedule cannot start before current one")
    if current is not None and current.work_schedule_id == schedule.id:
        await session.commit()
        return current
    if current is not None and payload.effective_from == current.effective_from:
        current.work_schedule_id = schedule.id
        await _audit(session, user, "schedule_assignment.correct", "schedule_assignment", current.id, rid)
        await session.commit()
        return current

    conflicts = select(ScheduleAssignment.id).where(
        ScheduleAssignment.employment_id == employment_id,
        ScheduleAssignment.active.is_(True),
        or_(
            ScheduleAssignment.effective_to.is_(None),
            ScheduleAssignment.effective_to >= payload.effective_from,
        ),
    )
    if current is not None:
        conflicts = conflicts.where(ScheduleAssignment.id != current.id)
    if await session.scalar(conflicts.limit(1)) is not None:
        raise HTTPException(status_code=409, detail="Schedule assignment overlaps another period")
    if current is not None:
        current.effective_to = payload.effective_from - timedelta(days=1)
        await session.flush()
    row = ScheduleAssignment(
        employment_id=employment_id,
        work_schedule_id=schedule.id,
        effective_from=payload.effective_from,
    )
    session.add(row)
    await session.flush()
    await _audit(session, user, "schedule_assignment.replace", "schedule_assignment", row.id, rid)
    await session.commit()
    return row


@employments_router.get(
    "/{employment_id}/schedule-assignments", response_model=list[ScheduleAssignmentOut]
)
async def list_schedule_assignments(
    employment_id: uuid.UUID,
    user: User = Depends(deps.require_permission("schedules.read")),
    session: AsyncSession = Depends(get_db),
) -> list[ScheduleAssignment]:
    await access_svc.require_employment(session, user, employment_id)
    return list(
        (
            await session.execute(
                select(ScheduleAssignment)
                .where(ScheduleAssignment.employment_id == employment_id)
                .order_by(ScheduleAssignment.effective_from.desc())
            )
        ).scalars()
    )


enrollments_router = APIRouter(prefix="/enrollment-requests", tags=["enrollment-requests"])


def _worker_name(person: Person) -> str:
    return " ".join(
        part for part in (person.first_name, person.last_name, person.second_last_name) if part
    )


def _employment_is_current(employment: Employment, company: Company) -> bool:
    try:
        timezone = ZoneInfo(company.timezone)
    except ZoneInfoNotFoundError:
        timezone = ZoneInfo("UTC")
    today = datetime.now(timezone).date()
    return (
        employment.active
        and employment.started_on <= today
        and (employment.ended_on is None or employment.ended_on >= today)
    )


def _enrollment_out(
    row: EnrollmentRequest,
    employment: Employment,
    person: Person,
    company: Company,
    site: Site | None,
) -> EnrollmentRequestOut:
    return EnrollmentRequestOut(
        id=row.id,
        person_id=person.id,
        worker_name=_worker_name(person),
        employment_id=row.employment_id,
        employee_number=employment.employee_number,
        company_name=company.trade_name or company.legal_name,
        site_name=site.name if site else None,
        position=employment.position,
        device_id=row.device_id,
        methods=list((row.methods or {}).get("requested", [])),
        fingerprint_positions=list((row.methods or {}).get("fingerprint_positions", [])),
        status=row.status,
        requested_by=row.requested_by,
        approved_by=row.approved_by,
        completed_by=row.completed_by,
        identity_verified_by=row.identity_verified_by,
        identity_verified_at=row.identity_verified_at,
        identity_verification_reference=row.identity_verification_reference,
        consent_recorded_by=row.consent_recorded_by,
        consent_recorded_at=row.consent_recorded_at,
        consent_reference=row.consent_reference,
        note=row.note,
    )


def _enrollment_context_query() -> Select[tuple[Employment, Person, Company, Site]]:
    return (
        select(Employment, Person, Company, Site)
        .join(Person, Employment.person_id == Person.id)
        .join(Company, Employment.company_id == Company.id)
        .outerjoin(Site, Employment.site_id == Site.id)
    )


@enrollments_router.get("/eligible-workers", response_model=list[EnrollmentCandidateOut])
async def list_enrollment_candidates(
    device_id: uuid.UUID,
    user: User = Depends(deps.require_permission("enrollments.write")),
    session: AsyncSession = Depends(get_db),
) -> list[EnrollmentCandidateOut]:
    device = await access_svc.require_device(session, user, device_id)
    allowed_company_ids = await access_svc.company_ids(session, user)
    query = _enrollment_context_query().where(
        Employment.company_id.in_(allowed_company_ids),
        Employment.active.is_(True),
        Person.active.is_(True),
    )
    if device.site_id is not None:
        device_site = await session.get(Site, device.site_id)
        if device_site is None:
            raise HTTPException(status_code=404, detail="Device site not found")
        await access_svc.require_company(session, user, device_site.company_id)
        query = query.where(Employment.company_id == device_site.company_id)

    rows = (await session.execute(query.order_by(Person.last_name, Person.first_name))).tuples()
    candidates: list[EnrollmentCandidateOut] = []
    for employment, person, company, site in rows:
        if not _employment_is_current(employment, company):
            continue
        candidates.append(
            EnrollmentCandidateOut(
                person_id=person.id,
                worker_name=_worker_name(person),
                employment_id=employment.id,
                employee_number=employment.employee_number,
                company_id=company.id,
                company_name=company.trade_name or company.legal_name,
                site_name=site.name if site else None,
                position=employment.position,
            )
        )
    return candidates


@enrollments_router.get("", response_model=list[EnrollmentRequestOut])
async def list_enrollment_requests(
    employment_id: uuid.UUID | None = None,
    device_id: uuid.UUID | None = None,
    user: User = Depends(deps.require_permission("enrollments.read")),
    session: AsyncSession = Depends(get_db),
) -> list[EnrollmentRequestOut]:
    query = (
        select(EnrollmentRequest, Employment, Person, Company, Site)
        .join(Employment, EnrollmentRequest.employment_id == Employment.id)
        .join(Person, Employment.person_id == Person.id)
        .join(Company, Employment.company_id == Company.id)
        .outerjoin(Site, Employment.site_id == Site.id)
        .where(Employment.company_id.in_(await access_svc.company_ids(session, user)))
        .order_by(EnrollmentRequest.created_at.desc())
        .limit(200)
    )
    if employment_id:
        await access_svc.require_employment(session, user, employment_id)
        query = query.where(EnrollmentRequest.employment_id == employment_id)
    if device_id:
        await access_svc.require_device(session, user, device_id)
        query = query.where(EnrollmentRequest.device_id == device_id)
    rows = (await session.execute(query)).tuples()
    return [
        _enrollment_out(request, employment, person, company, site)
        for request, employment, person, company, site in rows
    ]


@enrollments_router.post("", response_model=EnrollmentRequestOut, status_code=201)
async def create_enrollment_request(
    payload: EnrollmentRequestIn,
    user: User = Depends(deps.require_permission("enrollments.write")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> EnrollmentRequestOut:
    device = await access_svc.require_device(session, user, payload.device_id)
    if payload.person_id is None and payload.employment_id is None:
        raise HTTPException(status_code=422, detail="Select a worker to enroll")

    device_site = await session.get(Site, device.site_id) if device.site_id else None
    if device.site_id is not None and device_site is None:
        raise HTTPException(status_code=404, detail="Device site not found")

    if payload.employment_id is not None:
        employment = await access_svc.require_employment(session, user, payload.employment_id)
        context = await session.execute(
            _enrollment_context_query().where(Employment.id == employment.id)
        )
        context_row = context.tuples().one_or_none()
        if context_row is None:
            raise HTTPException(status_code=404, detail="Worker not found")
        employment, person, company, employment_site = context_row
        if payload.person_id is not None and payload.person_id != person.id:
            raise HTTPException(status_code=422, detail="Worker and employment do not match")
    else:
        if payload.person_id is None:
            raise HTTPException(status_code=422, detail="Select a worker to enroll")
        person = await access_svc.require_person(session, user, payload.person_id)
        query = _enrollment_context_query().where(
            Employment.person_id == person.id,
            Employment.company_id.in_(await access_svc.company_ids(session, user)),
            Employment.active.is_(True),
        )
        if device_site is not None:
            query = query.where(Employment.company_id == device_site.company_id)
        possible_contexts = (await session.execute(query)).tuples()
        current_contexts = [
            context
            for context in possible_contexts
            if _employment_is_current(context[0], context[2])
        ]
        if not current_contexts:
            raise HTTPException(
                status_code=422,
                detail="Worker needs a current employment in the device company",
            )
        if len(current_contexts) > 1:
            raise HTTPException(
                status_code=409,
                detail="Select the company employment for this worker",
            )
        employment, person, company, employment_site = current_contexts[0]

    if not person.active:
        raise HTTPException(status_code=422, detail="Inactive workers cannot be enrolled")
    if not _employment_is_current(employment, company):
        raise HTTPException(
            status_code=422,
            detail="Enrollment requires a current employment",
        )
    if device_site is not None and device_site.company_id != employment.company_id:
        raise HTTPException(status_code=422, detail="Device belongs to another company")
    allowed_methods = {"face", "fingerprint", "palm", "card", "password"}
    methods = {method.lower() for method in payload.methods}
    if not methods.issubset(allowed_methods):
        raise HTTPException(status_code=422, detail="Unsupported enrollment method")
    allowed_fingers = {
        "left_little",
        "left_ring",
        "left_middle",
        "left_index",
        "left_thumb",
        "right_thumb",
        "right_index",
        "right_middle",
        "right_ring",
        "right_little",
    }
    fingers = {position.lower() for position in payload.fingerprint_positions}
    if not fingers.issubset(allowed_fingers) or len(fingers) != len(payload.fingerprint_positions):
        raise HTTPException(status_code=422, detail="Unsupported or duplicate fingerprint position")
    if "fingerprint" in methods and not fingers:
        raise HTTPException(status_code=422, detail="Select at least one fingerprint position")
    if fingers and "fingerprint" not in methods:
        raise HTTPException(
            status_code=422, detail="Fingerprint positions require fingerprint method"
        )
    biometric_methods = {"face", "fingerprint", "palm"}
    if methods & biometric_methods and (
        not payload.consent_obtained or not payload.consent_reference
    ):
        raise HTTPException(
            status_code=422,
            detail="Biometric enrollment requires recorded consent and its reference",
        )
    row = EnrollmentRequest(
        employment_id=employment.id,
        device_id=device.id,
        methods={"requested": sorted(methods), "fingerprint_positions": sorted(fingers)},
        requested_by=user.id,
        consent_recorded_by=user.id if payload.consent_obtained else None,
        consent_recorded_at=datetime.now(UTC) if payload.consent_obtained else None,
        consent_reference=payload.consent_reference,
        note=payload.note,
    )
    session.add(row)
    await session.flush()
    await _audit(session, user, "enrollment_request.create", "enrollment_request", row.id, rid)
    await session.commit()
    return _enrollment_out(row, employment, person, company, employment_site)


@enrollments_router.patch("/{request_id}", response_model=EnrollmentRequestOut)
async def update_enrollment_request(
    request_id: uuid.UUID,
    payload: EnrollmentRequestStatusIn,
    user: User = Depends(deps.require_permission("enrollments.approve")),
    session: AsyncSession = Depends(get_db),
    rid: str = Depends(deps.request_id),
) -> EnrollmentRequestOut:
    row = await session.get(EnrollmentRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Enrollment request not found")
    await access_svc.require_employment(session, user, row.employment_id)
    transitions = {
        "requested": {"identity_verified", "rejected"},
        "identity_verified": {"approved", "rejected"},
        "approved": {"awaiting_device_enrollment", "rejected", "revoked"},
        "awaiting_device_enrollment": {"verification_pending", "rejected", "revoked"},
        "verification_pending": {"completed", "rejected", "revoked"},
        "completed": {"revoked"},
        "rejected": set(),
        "revoked": set(),
    }
    if payload.status not in transitions.get(row.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid enrollment transition: {row.status} -> {payload.status}",
        )
    if payload.status in {"identity_verified", "approved"} and row.requested_by == user.id:
        raise HTTPException(
            status_code=409,
            detail="The requester cannot verify identity or approve the same enrollment",
        )
    if payload.status == "identity_verified":
        if not payload.verification_reference:
            raise HTTPException(
                status_code=422, detail="Identity verification reference is required"
            )
        row.identity_verified_by = user.id
        row.identity_verified_at = datetime.now(UTC)
        row.identity_verification_reference = payload.verification_reference
    row.status = payload.status
    if payload.note is not None:
        row.note = payload.note
    if payload.status == "approved":
        if row.identity_verified_by is None:
            raise HTTPException(status_code=409, detail="Identity must be verified before approval")
        row.approved_by = user.id
    if payload.status == "completed":
        row.completed_by = user.id
    await _audit(session, user, "enrollment_request.update", "enrollment_request", row.id, rid)
    await session.commit()
    context = (
        await session.execute(
            _enrollment_context_query().where(Employment.id == row.employment_id)
        )
    ).tuples()
    employment, person, company, site = context.one()
    return _enrollment_out(row, employment, person, company, site)

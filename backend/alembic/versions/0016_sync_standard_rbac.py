"""Synchronize the complete standard RBAC catalog after HR modules were introduced.

Earlier HR migrations added endpoints before their non-device permissions were
persisted on already-running installations.  This is deliberately additive:
custom permissions, custom roles and user assignments are left untouched.
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, insert

from alembic import op

revision = "0016_sync_standard_rbac"
down_revision = "0015_overtime_governance"
branch_labels = None
depends_on = None


PERMISSIONS = (
    "devices.read",
    "devices.write",
    "devices.delete",
    "attendance.read",
    "attendance.write",
    "attendance.export",
    "device_users.read",
    "device_users.write",
    "device_users.delete",
    "commands.read",
    "commands.execute",
    "users.read",
    "users.write",
    "users.delete",
    "audit.read",
    "companies.read",
    "companies.write",
    "sites.read",
    "sites.write",
    "people.read",
    "people.write",
    "people.sensitive.read",
    "people.sensitive.write",
    "employments.read",
    "employments.write",
    "payroll.read",
    "payroll.write",
    "schedules.read",
    "schedules.write",
    "enrollments.read",
    "enrollments.write",
    "enrollments.approve",
    "overtime.read",
    "overtime.request",
    "overtime.review",
    "overtime.approve",
)

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "admin": PERMISSIONS,
    "operator": (
        "devices.read",
        "devices.write",
        "attendance.read",
        "attendance.write",
        "attendance.export",
        "device_users.read",
        "device_users.write",
        "device_users.delete",
        "commands.read",
        "commands.execute",
        "companies.read",
        "sites.read",
        "people.read",
        "employments.read",
        "schedules.read",
        "enrollments.read",
        "overtime.read",
    ),
    "viewer": (
        "devices.read",
        "attendance.read",
        "attendance.export",
        "device_users.read",
        "commands.read",
    ),
    "hr": (
        "attendance.read",
        "attendance.write",
        "attendance.export",
        "companies.read",
        "sites.read",
        "people.read",
        "people.write",
        "employments.read",
        "employments.write",
        "schedules.read",
        "schedules.write",
        "overtime.read",
        "overtime.request",
        "overtime.review",
    ),
    "director": ("attendance.read", "companies.read", "overtime.read", "overtime.approve"),
}


def upgrade() -> None:
    bind = op.get_bind()
    permissions = sa.table(
        "permissions",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
    )
    roles = sa.table(
        "roles",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", UUID(as_uuid=True)),
        sa.column("permission_id", UUID(as_uuid=True)),
    )

    bind.execute(
        insert(permissions)
        .values([{"id": uuid4(), "code": code, "description": code} for code in PERMISSIONS])
        .on_conflict_do_nothing(index_elements=["code"])
    )
    bind.execute(
        insert(roles)
        .values(
            [
                {"id": uuid4(), "name": name, "description": f"Standard {name} role"}
                for name in ROLE_PERMISSIONS
            ]
        )
        .on_conflict_do_nothing(index_elements=["name"])
    )

    role_ids = dict(bind.execute(sa.select(roles.c.name, roles.c.id)).all())
    permission_ids = dict(bind.execute(sa.select(permissions.c.code, permissions.c.id)).all())
    bindings = [
        {"role_id": role_ids[role], "permission_id": permission_ids[code]}
        for role, codes in ROLE_PERMISSIONS.items()
        for code in codes
    ]
    bind.execute(
        insert(role_permissions)
        .values(bindings)
        .on_conflict_do_nothing(index_elements=["role_id", "permission_id"])
    )


def downgrade() -> None:
    # Additive synchronization intentionally does not remove shared RBAC data.
    pass

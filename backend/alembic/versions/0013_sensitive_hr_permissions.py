"""Separate ordinary HR access from protected Mexican identifiers."""

from __future__ import annotations

from alembic import op

revision = "0013_sensitive_hr_permissions"
down_revision = "0012_user_business_scopes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
INSERT INTO permissions (id, code, description, created_at, updated_at)
VALUES
  ('61c51c37-53b8-4ecb-a4ed-05cb508722c1'::uuid, 'people.sensitive.read', 'Read protected HR identifiers', now(), now()),
  ('12d4c079-8c4e-4716-879b-2e5e52debc8a'::uuid, 'people.sensitive.write', 'Write protected HR identifiers', now(), now())
ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
INSERT INTO role_permissions (role_id, permission_id)
SELECT roles.id, permissions.id
FROM roles CROSS JOIN permissions
WHERE roles.name = 'admin'
  AND permissions.code IN ('people.sensitive.read', 'people.sensitive.write')
ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM permissions WHERE code IN ('people.sensitive.read', 'people.sensitive.write')"
    )

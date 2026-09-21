"""Add auditable daily HR attendance adjustments."""

from __future__ import annotations

from alembic import op

revision = "0010_attendance_adjustments"
down_revision = "0009_business_addresses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE attendance_adjustments (
  id UUID PRIMARY KEY,
  employment_id UUID NOT NULL REFERENCES employments(id) ON DELETE RESTRICT,
  attendance_date DATE NOT NULL,
  entry_at TIMESTAMPTZ NULL,
  meal_out_at TIMESTAMPTZ NULL,
  meal_in_at TIMESTAMPTZ NULL,
  exit_at TIMESTAMPTZ NULL,
  absence_kind VARCHAR(20) NULL,
  reason VARCHAR(500) NOT NULL,
  created_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  updated_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_attendance_adjustments_absence_kind
    CHECK (absence_kind IS NULL OR absence_kind IN ('justified', 'unjustified')),
  CONSTRAINT uq_attendance_adjustments_day UNIQUE (employment_id, attendance_date)
)
        """
    )
    op.execute(
        "CREATE INDEX ix_attendance_adjustments_employment_day ON attendance_adjustments(employment_id, attendance_date)"
    )
    # The separate permission avoids granting attendance correction to viewers.
    op.execute(
        """
INSERT INTO permissions (id, code, description, created_at, updated_at)
SELECT 'e3bb84a5-f5c2-4a2f-a272-c38c46988df1'::uuid, 'attendance.write', 'attendance.write', now(), now()
WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'attendance.write')
        """
    )
    op.execute(
        """
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
WHERE r.name IN ('admin', 'operator') AND p.code = 'attendance.write'
ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS attendance_adjustments")
    op.execute("DELETE FROM permissions WHERE code = 'attendance.write'")

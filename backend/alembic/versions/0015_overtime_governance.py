"""Add governed overtime candidates and dual approval permissions."""

from __future__ import annotations

from alembic import op

revision = "0015_overtime_governance"
down_revision = "0014_enrollment_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE overtime_requests (
  id UUID PRIMARY KEY,
  employment_id UUID NOT NULL REFERENCES employments(id) ON DELETE RESTRICT,
  attendance_date DATE NOT NULL,
  source VARCHAR(16) NOT NULL,
  status VARCHAR(24) NOT NULL DEFAULT 'pending_hr',
  scheduled_exit_at TIMESTAMPTZ NULL,
  detected_exit_at TIMESTAMPTZ NULL,
  minutes INTEGER NOT NULL,
  reviewed_minutes INTEGER NULL,
  authorized_minutes INTEGER NULL,
  reason VARCHAR(500) NOT NULL,
  created_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  reviewed_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at TIMESTAMPTZ NULL,
  review_note VARCHAR(500) NULL,
  authorized_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  authorized_at TIMESTAMPTZ NULL,
  authorization_note VARCHAR(500) NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_overtime_requests_source CHECK (source IN ('detected', 'manual')),
  CONSTRAINT ck_overtime_requests_status CHECK (status IN ('pending_hr', 'pending_direction', 'approved', 'rejected', 'cancelled')),
  CONSTRAINT ck_overtime_requests_minutes CHECK (minutes BETWEEN 1 AND 720),
  CONSTRAINT ck_overtime_requests_reviewed_minutes CHECK (reviewed_minutes IS NULL OR reviewed_minutes BETWEEN 1 AND 720),
  CONSTRAINT ck_overtime_requests_authorized_minutes CHECK (authorized_minutes IS NULL OR authorized_minutes BETWEEN 1 AND 720),
  CONSTRAINT uq_overtime_requests_day UNIQUE (employment_id, attendance_date)
)
        """
    )
    op.execute(
        "CREATE INDEX ix_overtime_requests_employment_day ON overtime_requests(employment_id, attendance_date)"
    )
    op.execute("CREATE INDEX ix_overtime_requests_status ON overtime_requests(status)")
    op.execute(
        """
INSERT INTO permissions (id, code, description, created_at, updated_at)
VALUES
  ('8c8f4a4b-7741-4adb-a225-e87c0dc49751'::uuid, 'overtime.read', 'Read overtime candidates', now(), now()),
  ('a53c9936-309e-4e55-853f-cb3312f6a5d2'::uuid, 'overtime.request', 'Create overtime candidates', now(), now()),
  ('6a9699be-729b-4d48-b09b-1640cd88cf5d'::uuid, 'overtime.review', 'Review overtime candidates as HR', now(), now()),
  ('92ef3441-1e13-4da9-ac1b-2c6c39004b16'::uuid, 'overtime.approve', 'Authorize overtime candidates as direction', now(), now())
ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
INSERT INTO roles (id, name, description, created_at, updated_at)
VALUES
  ('ad77f965-4e54-4aa0-b2ec-15b4f3abbd4a'::uuid, 'hr', 'Human resources', now(), now()),
  ('7f5ad016-3ea0-4f79-b048-e9371a7c0f83'::uuid, 'director', 'Direction approval', now(), now())
ON CONFLICT (name) DO NOTHING
        """
    )
    op.execute(
        """
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
WHERE (r.name = 'admin' AND p.code IN ('overtime.read', 'overtime.request', 'overtime.review', 'overtime.approve'))
   OR (r.name = 'operator' AND p.code IN ('overtime.read'))
   OR (r.name = 'hr' AND p.code IN ('attendance.read', 'attendance.write', 'attendance.export', 'companies.read', 'sites.read', 'people.read', 'people.write', 'employments.read', 'employments.write', 'schedules.read', 'schedules.write', 'overtime.read', 'overtime.request', 'overtime.review'))
   OR (r.name = 'director' AND p.code IN ('attendance.read', 'companies.read', 'overtime.read', 'overtime.approve'))
ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE role_id IN (SELECT id FROM roles WHERE name IN ('hr', 'director'))"
    )
    op.execute("DELETE FROM roles WHERE name IN ('hr', 'director')")
    op.execute(
        "DELETE FROM permissions WHERE code IN ('overtime.read', 'overtime.request', 'overtime.review', 'overtime.approve')"
    )
    op.execute("DROP TABLE overtime_requests")

"""Add consent, identity verification and controlled enrollment workflow."""

from __future__ import annotations

from alembic import op

revision = "0014_enrollment_governance"
down_revision = "0013_sensitive_hr_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE enrollment_requests DROP CONSTRAINT ck_enrollment_requests_status")
    op.execute(
        """
ALTER TABLE enrollment_requests
  ADD COLUMN identity_verified_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN identity_verified_at TIMESTAMPTZ NULL,
  ADD COLUMN identity_verification_reference VARCHAR(255) NULL,
  ADD COLUMN consent_recorded_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN consent_recorded_at TIMESTAMPTZ NULL,
  ADD COLUMN consent_reference VARCHAR(255) NULL,
  ADD CONSTRAINT ck_enrollment_requests_status CHECK (
    status IN ('requested','identity_verified','approved','awaiting_device_enrollment',
               'verification_pending','completed','rejected','revoked')
  )
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE enrollment_requests DROP CONSTRAINT ck_enrollment_requests_status")
    op.execute(
        """
ALTER TABLE enrollment_requests
  DROP COLUMN consent_reference,
  DROP COLUMN consent_recorded_at,
  DROP COLUMN consent_recorded_by,
  DROP COLUMN identity_verification_reference,
  DROP COLUMN identity_verified_at,
  DROP COLUMN identity_verified_by,
  ADD CONSTRAINT ck_enrollment_requests_status CHECK (
    status IN ('requested','approved','awaiting_device_enrollment',
               'verification_pending','completed','rejected','revoked')
  )
        """
    )

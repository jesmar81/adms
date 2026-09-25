"""Remove biometric consent fields from enrollment requests."""

from alembic import op

revision = "0018_remove_enrollment_consent"
down_revision = "0017_automatic_schedule_exit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
ALTER TABLE enrollment_requests
  DROP COLUMN consent_reference,
  DROP COLUMN consent_recorded_at,
  DROP COLUMN consent_recorded_by
        """
    )


def downgrade() -> None:
    op.execute(
        """
ALTER TABLE enrollment_requests
  ADD COLUMN consent_recorded_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN consent_recorded_at TIMESTAMPTZ NULL,
  ADD COLUMN consent_reference VARCHAR(255) NULL
        """
    )

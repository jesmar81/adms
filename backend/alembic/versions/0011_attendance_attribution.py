"""Route each raw attendance mark to at most one employment."""

from __future__ import annotations

from alembic import op

revision = "0011_attendance_attribution"
down_revision = "0010_attendance_adjustments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE attendance_attributions (
  id UUID PRIMARY KEY,
  attendance_log_id UUID NOT NULL REFERENCES attendance_logs(id) ON DELETE CASCADE,
  employment_id UUID NULL REFERENCES employments(id) ON DELETE RESTRICT,
  status VARCHAR(20) NOT NULL,
  method VARCHAR(40) NOT NULL DEFAULT 'device_site',
  reason VARCHAR(255) NULL,
  resolved_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  resolved_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_attendance_attributions_log UNIQUE (attendance_log_id),
  CONSTRAINT ck_attendance_attributions_status
    CHECK (status IN ('assigned', 'ambiguous', 'unassigned')),
  CONSTRAINT ck_attendance_attributions_employment CHECK (
    (status = 'assigned' AND employment_id IS NOT NULL) OR
    (status IN ('ambiguous', 'unassigned') AND employment_id IS NULL)
  )
)
        """
    )
    op.execute(
        "CREATE INDEX ix_attendance_attributions_employment ON attendance_attributions(employment_id)"
    )
    op.execute("CREATE INDEX ix_attendance_attributions_status ON attendance_attributions(status)")
    # Historical rows cannot be attributed safely without replaying the same
    # business rules and reviewing ambiguities. Preserve them for the explicit
    # reconciliation queue; never guess an employment during migration.
    op.execute(
        """
INSERT INTO attendance_attributions (
  id, attendance_log_id, employment_id, status, method, reason, created_at, updated_at
)
SELECT gen_random_uuid(), id, NULL, 'unassigned', 'migration',
       'Historical mark requires reconciliation', now(), now()
FROM attendance_logs
ON CONFLICT (attendance_log_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS attendance_attributions")

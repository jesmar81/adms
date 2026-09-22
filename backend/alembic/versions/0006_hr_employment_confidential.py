"""Add employment context and confidential payroll/IMSS profile."""

from __future__ import annotations

from alembic import op

revision = "0006_hr_employment_confidential"
down_revision = "0005_hr_profile_calendars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE person_sensitive_identifiers ADD COLUMN fiscal_name_encrypted TEXT NULL"
    )
    op.execute("ALTER TABLE person_sensitive_identifiers ADD COLUMN tax_regime_encrypted TEXT NULL")
    op.execute(
        "ALTER TABLE person_sensitive_identifiers ADD COLUMN fiscal_postal_code_encrypted TEXT NULL"
    )
    op.execute("ALTER TABLE employments ADD COLUMN site_id UUID NULL")
    op.execute("ALTER TABLE employments ADD COLUMN employment_relation_type VARCHAR(80) NULL")
    op.execute("ALTER TABLE employments ADD COLUMN job_category VARCHAR(100) NULL")
    op.execute("ALTER TABLE employments ADD COLUMN work_location VARCHAR(150) NULL")
    op.execute("ALTER TABLE employments ADD COLUMN probation_ends_on DATE NULL")
    op.execute(
        "ALTER TABLE employments ADD CONSTRAINT fk_employments_site_id "
        "FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE SET NULL"
    )
    op.execute("CREATE INDEX ix_employments_site ON employments(site_id)")
    op.execute(
        """
CREATE TABLE employment_compensations (
id UUID PRIMARY KEY,
employment_id UUID NOT NULL,
daily_salary NUMERIC(12,2) NULL,
integrated_daily_salary NUMERIC(12,2) NULL,
pay_frequency VARCHAR(32) NULL,
payment_method VARCHAR(32) NULL,
bank_clabe_encrypted TEXT NULL,
imss_umf VARCHAR(16) NULL,
imss_worker_type VARCHAR(16) NULL,
imss_salary_type VARCHAR(16) NULL,
imss_workday_type VARCHAR(16) NULL,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_employment_compensations_employment_id FOREIGN KEY (employment_id) REFERENCES employments(id) ON DELETE CASCADE,
CONSTRAINT uq_employment_compensations_employment UNIQUE (employment_id)
)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS employment_compensations")
    op.execute("DROP INDEX IF EXISTS ix_employments_site")
    op.execute("ALTER TABLE employments DROP CONSTRAINT IF EXISTS fk_employments_site_id")
    for column in (
        "probation_ends_on",
        "work_location",
        "job_category",
        "employment_relation_type",
        "site_id",
    ):
        op.execute(f"ALTER TABLE employments DROP COLUMN IF EXISTS {column}")
    op.execute(
        "ALTER TABLE person_sensitive_identifiers DROP COLUMN IF EXISTS fiscal_postal_code_encrypted"
    )
    op.execute(
        "ALTER TABLE person_sensitive_identifiers DROP COLUMN IF EXISTS tax_regime_encrypted"
    )
    op.execute(
        "ALTER TABLE person_sensitive_identifiers DROP COLUMN IF EXISTS fiscal_name_encrypted"
    )

"""Expand the HR profile and add company holiday calendars."""

from __future__ import annotations

from alembic import op

revision = "0005_hr_profile_calendars"
down_revision = "0004_corporate_hr_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE people ADD COLUMN birth_date DATE NULL")
    op.execute("ALTER TABLE people ADD COLUMN sex VARCHAR(32) NULL")
    op.execute("ALTER TABLE people ADD COLUMN marital_status VARCHAR(32) NULL")
    op.execute("ALTER TABLE people ADD COLUMN nationality VARCHAR(80) NULL")
    op.execute("ALTER TABLE people ADD COLUMN birth_state VARCHAR(100) NULL")
    op.execute("ALTER TABLE people ADD COLUMN address_street VARCHAR(150) NULL")
    op.execute("ALTER TABLE people ADD COLUMN address_ext_number VARCHAR(20) NULL")
    op.execute("ALTER TABLE people ADD COLUMN address_int_number VARCHAR(20) NULL")
    op.execute("ALTER TABLE people ADD COLUMN address_neighborhood VARCHAR(100) NULL")
    op.execute("ALTER TABLE people ADD COLUMN address_municipality VARCHAR(100) NULL")
    op.execute("ALTER TABLE people ADD COLUMN address_state VARCHAR(100) NULL")
    op.execute("ALTER TABLE people ADD COLUMN postal_code VARCHAR(10) NULL")
    op.execute("ALTER TABLE people ADD COLUMN emergency_contact_name VARCHAR(150) NULL")
    op.execute("ALTER TABLE people ADD COLUMN emergency_contact_phone VARCHAR(32) NULL")
    op.execute("ALTER TABLE people ADD COLUMN emergency_contact_relationship VARCHAR(80) NULL")
    op.execute(
        """
CREATE TABLE person_sensitive_identifiers (
id UUID PRIMARY KEY,
person_id UUID NOT NULL,
curp_encrypted TEXT NULL,
rfc_encrypted TEXT NULL,
nss_encrypted TEXT NULL,
curp_hash VARCHAR(64) NULL,
rfc_hash VARCHAR(64) NULL,
nss_hash VARCHAR(64) NULL,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_person_sensitive_identifiers_person_id FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE,
CONSTRAINT uq_person_sensitive_identifiers_person UNIQUE (person_id)
)
        """
    )
    op.execute("CREATE INDEX ix_person_sensitive_identifiers_curp_hash ON person_sensitive_identifiers(curp_hash)")
    op.execute("CREATE INDEX ix_person_sensitive_identifiers_rfc_hash ON person_sensitive_identifiers(rfc_hash)")
    op.execute("CREATE INDEX ix_person_sensitive_identifiers_nss_hash ON person_sensitive_identifiers(nss_hash)")
    op.execute(
        """
CREATE TABLE holidays (
id UUID PRIMARY KEY,
company_id UUID NOT NULL,
holiday_date DATE NOT NULL,
name VARCHAR(200) NOT NULL,
kind VARCHAR(20) NOT NULL,
source VARCHAR(80) NULL,
is_paid_rest BOOLEAN NOT NULL DEFAULT true,
generated BOOLEAN NOT NULL DEFAULT false,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_holidays_company_id FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE RESTRICT,
CONSTRAINT ck_holidays_kind CHECK (kind IN ('statutory','company','electoral')),
CONSTRAINT uq_holidays_company_date UNIQUE (company_id, holiday_date)
)
        """
    )
    op.execute("CREATE INDEX ix_holidays_company_date ON holidays(company_id, holiday_date)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS holidays")
    op.execute("DROP TABLE IF EXISTS person_sensitive_identifiers")
    for column in (
        "emergency_contact_relationship",
        "emergency_contact_phone",
        "emergency_contact_name",
        "postal_code",
        "address_state",
        "address_municipality",
        "address_neighborhood",
        "address_int_number",
        "address_ext_number",
        "address_street",
        "birth_state",
        "nationality",
        "marital_status",
        "sex",
        "birth_date",
    ):
        op.execute(f"ALTER TABLE people DROP COLUMN IF EXISTS {column}")

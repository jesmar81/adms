"""Normalize company and branch addresses without losing legacy branch text."""

from __future__ import annotations

from alembic import op

revision = "0009_business_addresses"
down_revision = "0008_person_photo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE addresses (
id UUID PRIMARY KEY,
company_id UUID NULL,
site_id UUID NULL,
street VARCHAR(150) NULL,
exterior_number VARCHAR(20) NULL,
interior_number VARCHAR(20) NULL,
neighborhood VARCHAR(100) NULL,
municipality VARCHAR(100) NULL,
state VARCHAR(100) NULL,
postal_code VARCHAR(5) NULL,
country VARCHAR(80) NOT NULL DEFAULT 'México',
reference_notes VARCHAR(250) NULL,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_addresses_company_id FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
CONSTRAINT fk_addresses_site_id FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
CONSTRAINT ck_addresses_exactly_one_owner CHECK (
  (company_id IS NOT NULL AND site_id IS NULL) OR (company_id IS NULL AND site_id IS NOT NULL)
),
CONSTRAINT uq_addresses_company UNIQUE (company_id),
CONSTRAINT uq_addresses_site UNIQUE (site_id)
)
        """
    )
    op.execute("CREATE INDEX ix_addresses_company ON addresses(company_id)")
    op.execute("CREATE INDEX ix_addresses_site ON addresses(site_id)")
    # Preserve the former free-text site address as operational references.
    op.execute(
        """
INSERT INTO addresses (id, site_id, reference_notes)
SELECT (
  substr(md5(id::text || 'business-address'), 1, 8) || '-' ||
  substr(md5(id::text || 'business-address'), 9, 4) || '-' ||
  substr(md5(id::text || 'business-address'), 13, 4) || '-' ||
  substr(md5(id::text || 'business-address'), 17, 4) || '-' ||
  substr(md5(id::text || 'business-address'), 21, 12)
)::uuid, id, left(address, 250)
FROM sites
WHERE address IS NOT NULL AND btrim(address) <> ''
        """
    )
    op.execute("ALTER TABLE sites DROP COLUMN address")


def downgrade() -> None:
    op.execute("ALTER TABLE sites ADD COLUMN address TEXT NULL")
    op.execute(
        """
UPDATE sites
SET address = addresses.reference_notes
FROM addresses
WHERE addresses.site_id = sites.id
        """
    )
    op.execute("DROP TABLE IF EXISTS addresses")

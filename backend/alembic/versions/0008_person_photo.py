"""Store one protected profile photo for each worker."""

from __future__ import annotations

from alembic import op

revision = "0008_person_photo"
down_revision = "0007_one_current_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE person_photos (
id UUID PRIMARY KEY,
person_id UUID NOT NULL,
image_data BYTEA NOT NULL,
content_type VARCHAR(20) NOT NULL,
size_bytes INTEGER NOT NULL,
sha256 VARCHAR(64) NOT NULL,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
CONSTRAINT fk_person_photos_person_id FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE,
CONSTRAINT uq_person_photos_person UNIQUE (person_id)
)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS person_photos")

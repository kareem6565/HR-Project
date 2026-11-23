"""Record resume text extraction source and OCR confidence."""

import sqlalchemy as sa

from alembic import op

revision = "032_resume_ocr_metadata"
down_revision = "031_a5_advisory_prerank"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_resumes_status", "resumes", type_="check")
    op.create_check_constraint(
        "ck_resumes_status",
        "resumes",
        "status IN ('uploaded', 'text_extracted', 'profile_extracted', "
        "'needs_manual_review', 'archived')",
    )
    op.add_column(
        "resumes",
        sa.Column(
            "extraction_source", sa.String(length=24), server_default="text_layer", nullable=False
        ),
    )
    op.add_column("resumes", sa.Column("extraction_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    op.execute("UPDATE resumes SET status = 'text_extracted' WHERE status = 'needs_manual_review'")
    op.drop_column("resumes", "extraction_confidence")
    op.drop_column("resumes", "extraction_source")
    op.drop_constraint("ck_resumes_status", "resumes", type_="check")
    op.create_check_constraint(
        "ck_resumes_status",
        "resumes",
        "status IN ('uploaded', 'text_extracted', 'profile_extracted', 'archived')",
    )

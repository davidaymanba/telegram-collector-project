"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

T = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def _dt() -> mysql.DATETIME:
    return mysql.DATETIME(fsp=6)


def upgrade() -> None:
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_message_id", sa.BigInteger(), nullable=False),
        sa.Column("last_run_at", _dt(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.Column("created_at", _dt(), nullable=False),
        sa.Column("updated_at", _dt(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_channels"),
        sa.UniqueConstraint("telegram_id", name="uq_channels_telegram_id"),
        sa.UniqueConstraint("username", name="uq_channels_username"),
        **T,
    )
    op.create_index("ix_channels_enabled", "channels", ["enabled"])

    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("created_at", _dt(), nullable=False),
        sa.Column("updated_at", _dt(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_subjects"),
        sa.UniqueConstraint("code", name="uq_subjects_code"),
        **T,
    )

    op.create_table(
        "processing_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", _dt(), nullable=False),
        sa.Column("finished_at", _dt(), nullable=True),
        sa.Column("new_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("classified_count", sa.Integer(), nullable=False),
        sa.Column("unclassified_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("unsupported_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_processing_runs"),
        **T,
    )
    op.create_index("ix_processing_runs_kind", "processing_runs", ["kind"])
    op.create_index("ix_processing_runs_started_at", "processing_runs", ["started_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("message_date", _dt(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("media_type", sa.String(32), nullable=False),
        sa.Column("file_name", sa.String(512), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("telegram_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", _dt(), nullable=False),
        sa.Column("updated_at", _dt(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE",
                                name="fk_messages_channel_id_channels"),
        sa.UniqueConstraint("channel_id", "telegram_message_id",
                            name="uq_messages_channel_id_telegram_message_id"),
        **T,
    )
    op.create_index("ix_messages_message_date", "messages", ["message_date"])

    op.create_table(
        "collected_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("telegram_document_id", sa.BigInteger(), nullable=True),
        sa.Column("duplicate_of_file_id", sa.Integer(), nullable=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("extension", sa.String(16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.CHAR(64), nullable=True),
        sa.Column("storage_path", sa.String(1024), nullable=True),
        sa.Column("extracted_text_path", sa.String(1024), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", _dt(), nullable=False),
        sa.Column("updated_at", _dt(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_collected_files"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE",
                                name="fk_collected_files_message_id_messages"),
        sa.ForeignKeyConstraint(["duplicate_of_file_id"], ["collected_files.id"],
                                ondelete="SET NULL",
                                name="fk_collected_files_duplicate_of_file_id_collected_files"),
        sa.UniqueConstraint("message_id", name="uq_collected_files_message_id"),
        **T,
    )
    op.create_index("ix_collected_files_telegram_document_id", "collected_files",
                    ["telegram_document_id"])
    op.create_index("ix_collected_files_sha256", "collected_files", ["sha256"])
    op.create_index("ix_collected_files_status_created", "collected_files",
                    ["status", "created_at"])
    op.create_index("ix_collected_files_extension", "collected_files", ["extension"])

    op.create_table(
        "classifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("subject_code", sa.String(32), nullable=True),
        sa.Column("content_type", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("classifier_version", sa.String(32), nullable=False),
        sa.Column("created_at", _dt(), nullable=False),
        sa.Column("updated_at", _dt(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_classifications"),
        sa.ForeignKeyConstraint(["file_id"], ["collected_files.id"], ondelete="CASCADE",
                                name="fk_classifications_file_id_collected_files"),
        sa.UniqueConstraint("file_id", name="uq_classifications_file_id"),
        **T,
    )
    op.create_index("ix_classifications_subject_type", "classifications",
                    ["subject_code", "content_type"])

    op.create_table(
        "processing_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("message", sa.String(1000), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", _dt(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_processing_logs"),
        sa.ForeignKeyConstraint(["file_id"], ["collected_files.id"], ondelete="CASCADE",
                                name="fk_processing_logs_file_id_collected_files"),
        sa.ForeignKeyConstraint(["run_id"], ["processing_runs.id"], ondelete="SET NULL",
                                name="fk_processing_logs_run_id_processing_runs"),
        **T,
    )
    op.create_index("ix_processing_logs_file_id", "processing_logs", ["file_id"])
    op.create_index("ix_processing_logs_run_id", "processing_logs", ["run_id"])


def downgrade() -> None:
    for table in ("processing_logs", "classifications", "collected_files", "messages",
                  "processing_runs", "subjects", "channels"):
        op.drop_table(table)

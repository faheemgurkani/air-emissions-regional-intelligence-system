"""Alerts: route_exposure_history, alert_log, saved_routes UPES columns

Revision ID: 002
Revises: 001
Create Date: 2025-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "route_exposure_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("upes_score", sa.Double(), nullable=False),
        sa.Column("max_upes_along_route", sa.Double(), nullable=True),
        sa.Column("score_source", sa.Text(), server_default="upes", nullable=False),
        sa.ForeignKeyConstraint(["route_id"], ["saved_routes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_route_exposure_history_route_id"), "route_exposure_history", ["route_id"], unique=False)
    op.create_index("ix_route_exposure_history_route_timestamp", "route_exposure_history", ["route_id", "timestamp"], unique=False)

    op.create_table(
        "alert_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("route_id", sa.Integer(), nullable=True),
        sa.Column("alert_type", sa.Text(), nullable=False),
        sa.Column("score_before", sa.Double(), nullable=True),
        sa.Column("score_after", sa.Double(), nullable=True),
        sa.Column("threshold", sa.Double(), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("notified_channels", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["route_id"], ["saved_routes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alert_log_user_id"), "alert_log", ["user_id"], unique=False)
    op.create_index(op.f("ix_alert_log_route_id"), "alert_log", ["route_id"], unique=False)
    op.create_index(op.f("ix_alert_log_created_at"), "alert_log", ["created_at"], unique=False)

    op.add_column("saved_routes", sa.Column("last_upes_score", sa.Double(), nullable=True))
    op.add_column("saved_routes", sa.Column("last_upes_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("saved_routes", "last_upes_updated_at")
    op.drop_column("saved_routes", "last_upes_score")
    op.drop_index(op.f("ix_alert_log_created_at"), table_name="alert_log")
    op.drop_index(op.f("ix_alert_log_route_id"), table_name="alert_log")
    op.drop_index(op.f("ix_alert_log_user_id"), table_name="alert_log")
    op.drop_table("alert_log")
    op.drop_index("ix_route_exposure_history_route_timestamp", table_name="route_exposure_history")
    op.drop_index(op.f("ix_route_exposure_history_route_id"), table_name="route_exposure_history")
    op.drop_table("route_exposure_history")

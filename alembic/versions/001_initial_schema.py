"""Initial schema: users, saved_routes, pollution_grid, netcdf_files + PostGIS

Revision ID: 001
Revises:
Create Date: 2025-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("notification_preferences", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("preferred_activity", sa.Text(), nullable=True),
        sa.Column("exposure_sensitivity_level", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.CheckConstraint(
            "preferred_activity IS NULL OR preferred_activity IN ('commute','jog','cycle')",
            name="users_preferred_activity_check",
        ),
        sa.CheckConstraint(
            "exposure_sensitivity_level IS NULL OR (exposure_sensitivity_level >= 1 AND exposure_sensitivity_level <= 5)",
            name="users_exposure_sensitivity_level_check",
        ),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "saved_routes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("origin_lat", sa.Double(), nullable=False),
        sa.Column("origin_lon", sa.Double(), nullable=False),
        sa.Column("dest_lat", sa.Double(), nullable=False),
        sa.Column("dest_lon", sa.Double(), nullable=False),
        sa.Column("activity_type", sa.Text(), nullable=True),
        sa.Column("last_computed_score", sa.Double(), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "activity_type IS NULL OR activity_type IN ('commute','jog','cycle')",
            name="saved_routes_activity_type_check",
        ),
    )
    op.create_index(op.f("ix_saved_routes_user_id"), "saved_routes", ["user_id"], unique=False)

    op.create_table(
        "pollution_grid",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gas_type", sa.Text(), nullable=False),
        sa.Column("geom", Geometry(geometry_type="POLYGON", srid=4326), nullable=False),
        sa.Column("pollution_value", sa.Double(), nullable=False),
        sa.Column("severity_level", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("severity_level >= 0", name="pollution_grid_severity_level_check"),
    )
    op.create_index(op.f("ix_pollution_grid_gas_type"), "pollution_grid", ["gas_type"], unique=False)
    op.create_index("idx_pollution_grid_time_gas", "pollution_grid", ["timestamp", "gas_type"], unique=False)
    op.execute(
        "CREATE INDEX idx_pollution_grid_geom ON pollution_grid USING GIST (geom)"
    )

    op.create_table(
        "netcdf_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("bucket_path", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gas_type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_netcdf_files_gas_type"), "netcdf_files", ["gas_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_netcdf_files_gas_type"), table_name="netcdf_files")
    op.drop_table("netcdf_files")
    op.drop_index("idx_pollution_grid_geom", table_name="pollution_grid")
    op.drop_index("idx_pollution_grid_time_gas", table_name="pollution_grid")
    op.drop_index(op.f("ix_pollution_grid_gas_type"), table_name="pollution_grid")
    op.drop_table("pollution_grid")
    op.drop_index(op.f("ix_saved_routes_user_id"), table_name="saved_routes")
    op.drop_table("saved_routes")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

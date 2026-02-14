"""
SQLAlchemy models with GeoAlchemy2 for PostGIS.
"""
from datetime import datetime
from typing import Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    notification_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    preferred_activity: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    exposure_sensitivity_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", onupdate="now()")

    __table_args__ = (
        CheckConstraint(
            "preferred_activity IS NULL OR preferred_activity IN ('commute','jog','cycle')",
            name="users_preferred_activity_check",
        ),
        CheckConstraint(
            "exposure_sensitivity_level IS NULL OR (exposure_sensitivity_level >= 1 AND exposure_sensitivity_level <= 5)",
            name="users_exposure_sensitivity_level_check",
        ),
    )

    saved_routes: Mapped[list["SavedRoute"]] = relationship("SavedRoute", back_populates="user", cascade="all, delete-orphan")


class SavedRoute(Base):
    __tablename__ = "saved_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    origin_lat: Mapped[float] = mapped_column(Double, nullable=False)
    origin_lon: Mapped[float] = mapped_column(Double, nullable=False)
    dest_lat: Mapped[float] = mapped_column(Double, nullable=False)
    dest_lon: Mapped[float] = mapped_column(Double, nullable=False)
    activity_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_computed_score: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

    __table_args__ = (
        CheckConstraint(
            "activity_type IS NULL OR activity_type IN ('commute','jog','cycle')",
            name="saved_routes_activity_type_check",
        ),
    )

    user: Mapped["User"] = relationship("User", back_populates="saved_routes")


class PollutionGrid(Base):
    __tablename__ = "pollution_grid"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gas_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    pollution_value: Mapped[float] = mapped_column(Double, nullable=False)
    severity_level: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

    __table_args__ = (
        CheckConstraint("severity_level >= 0", name="pollution_grid_severity_level_check"),
    )


class NetcdfFile(Base):
    __tablename__ = "netcdf_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    bucket_path: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gas_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

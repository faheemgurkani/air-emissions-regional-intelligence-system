"""
Pydantic schemas for API request/response validation.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


# ----- Auth -----
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    notification_preferences: Optional[dict] = None
    preferred_activity: Optional[str] = None
    exposure_sensitivity_level: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ----- Saved routes -----
class SavedRouteCreate(BaseModel):
    origin_lat: float = Field(..., ge=-90, le=90)
    origin_lon: float = Field(..., ge=-180, le=180)
    dest_lat: float = Field(..., ge=-90, le=90)
    dest_lon: float = Field(..., ge=-180, le=180)
    activity_type: Optional[str] = Field(None, pattern="^(commute|jog|cycle)$")


class SavedRouteUpdate(BaseModel):
    activity_type: Optional[str] = Field(None, pattern="^(commute|jog|cycle)$")
    last_computed_score: Optional[float] = None


class SavedRouteResponse(BaseModel):
    id: int
    user_id: int
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    activity_type: Optional[str] = None
    last_computed_score: Optional[float] = None
    last_updated_at: Optional[datetime] = None
    last_upes_score: Optional[float] = None
    last_upes_updated_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ----- User profile update (preferences, sensitivity) -----
class UserUpdate(BaseModel):
    notification_preferences: Optional[dict] = None  # e.g. {"email": true, "push": false, "in_app": true}
    exposure_sensitivity_level: Optional[int] = Field(None, ge=1, le=5)


# ----- Alerts -----
class AlertLogResponse(BaseModel):
    id: int
    user_id: int
    route_id: Optional[int] = None
    alert_type: str
    score_before: Optional[float] = None
    score_after: Optional[float] = None
    threshold: Optional[float] = None
    metadata: Optional[dict] = None
    created_at: datetime
    notified_channels: Optional[list] = None

    class Config:
        from_attributes = True

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class EmergencyContactCreate(BaseModel):
    name: str = Field(..., max_length=100)
    phone: str = Field(..., max_length=30)
    relationship: Optional[str] = Field(None, max_length=50)
    priority: int = 0
    is_primary: bool = False
    is_active: bool = True

class EmergencyContactUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    relationship: Optional[str] = Field(None, max_length=50)
    priority: Optional[int] = None
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None

class EmergencyContactResponse(BaseModel):
    id: str
    traveler_id: str
    name: str
    phone: str
    relationship: Optional[str] = None
    priority: int
    is_primary: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SafetyResource(BaseModel):
    id: str
    type: str # hospital, police, consulate
    name: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    distance_km: Optional[float] = None
    source: str
    is_synthetic: bool
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)

class EmergencyAlertCreate(BaseModel):
    trigger_source: str = Field(..., max_length=100)
    message: Optional[str] = Field(None, max_length=1000)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_shared: bool = False
    idempotency_key: str = Field(..., max_length=100)

class EmergencyAlertResponse(BaseModel):
    id: str
    traveler_id: str
    status: str
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    trigger_source: str
    message: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_shared: bool
    delivery_status: str
    idempotency_key: str

    model_config = ConfigDict(from_attributes=True)

class EmergencyAlertCancel(BaseModel):
    pass

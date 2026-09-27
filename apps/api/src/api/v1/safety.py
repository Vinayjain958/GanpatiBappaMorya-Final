from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from src.core.db import get_session
from src.api.v1.auth import require_traveler
from src.models.user import User

from src.schemas.safety import (
    EmergencyContactCreate,
    EmergencyContactUpdate,
    EmergencyContactResponse,
    SafetyResource,
    EmergencyAlertCreate,
    EmergencyAlertResponse,
    EmergencyAlertCancel
)
from src.services.safety import contacts as contacts_service
from src.services.safety import emergency_alerts as alerts_service
from src.services.safety import safety_resources as resources_service
from src.services.safety.safety_resources import InvalidRadiusError, SafetyResourceServiceError

router = APIRouter(prefix="/safety", tags=["safety"])

# --- Emergency Contacts ---

@router.get("/emergency-contacts", response_model=List[EmergencyContactResponse])
async def get_emergency_contacts(
    user: User = Depends(require_traveler),
    db: AsyncSession = Depends(get_session)
):
    return await contacts_service.get_emergency_contacts(db, user.traveler.id)

@router.post("/emergency-contacts", response_model=EmergencyContactResponse, status_code=status.HTTP_201_CREATED)
async def create_emergency_contact(
    contact_in: EmergencyContactCreate,
    user: User = Depends(require_traveler),
    db: AsyncSession = Depends(get_session)
):
    return await contacts_service.create_emergency_contact(db, user.traveler.id, contact_in)

@router.patch("/emergency-contacts/{contact_id}", response_model=EmergencyContactResponse)
async def update_emergency_contact(
    contact_id: str,
    contact_in: EmergencyContactUpdate,
    user: User = Depends(require_traveler),
    db: AsyncSession = Depends(get_session)
):
    return await contacts_service.update_emergency_contact(db, user.traveler.id, contact_id, contact_in)

@router.delete("/emergency-contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_emergency_contact(
    contact_id: str,
    user: User = Depends(require_traveler),
    db: AsyncSession = Depends(get_session)
):
    await contacts_service.delete_emergency_contact(db, user.traveler.id, contact_id)


# --- Safety Resources ---

@router.get("/resources/nearby", response_model=List[SafetyResource])
async def get_nearby_resources(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(5.0, gt=0),
    category: Optional[str] = Query(None, pattern="^(hospital|police|consulate)$"),
    user: User = Depends(require_traveler)
):
    try:
        return await resources_service.get_nearby_safety_resources(lat, lng, radius_km, category)
    except InvalidRadiusError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except SafetyResourceServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


# --- Emergency Alerts ---

@router.post("/emergency-alerts", response_model=EmergencyAlertResponse, status_code=status.HTTP_201_CREATED)
async def create_emergency_alert(
    alert_in: EmergencyAlertCreate,
    user: User = Depends(require_traveler),
    db: AsyncSession = Depends(get_session)
):
    return await alerts_service.create_emergency_alert(db, user.traveler.id, alert_in)

@router.get("/emergency-alerts", response_model=List[EmergencyAlertResponse])
async def get_emergency_alerts(
    user: User = Depends(require_traveler),
    db: AsyncSession = Depends(get_session)
):
    return await alerts_service.get_emergency_alerts(db, user.traveler.id)

@router.get("/emergency-alerts/{alert_id}", response_model=EmergencyAlertResponse)
async def get_emergency_alert(
    alert_id: str,
    user: User = Depends(require_traveler),
    db: AsyncSession = Depends(get_session)
):
    return await alerts_service.get_emergency_alert(db, user.traveler.id, alert_id)

@router.post("/emergency-alerts/{alert_id}/cancel", response_model=EmergencyAlertResponse)
async def cancel_emergency_alert(
    alert_id: str,
    user: User = Depends(require_traveler),
    db: AsyncSession = Depends(get_session)
):
    return await alerts_service.cancel_emergency_alert(db, user.traveler.id, alert_id)

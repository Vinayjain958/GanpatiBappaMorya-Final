import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from typing import List
from datetime import datetime, UTC
from sqlalchemy.exc import IntegrityError

from src.models.safety import EmergencyAlert
from src.schemas.safety import EmergencyAlertCreate
from src.services.safety.alert_adapters import InAppEmergencyAlertAdapter, WebhookEmergencyAlertAdapter

logger = logging.getLogger(__name__)

async def create_emergency_alert(db: AsyncSession, traveler_id: str, alert_in: EmergencyAlertCreate) -> EmergencyAlert:
    # Handle Idempotency
    stmt = select(EmergencyAlert).where(
        EmergencyAlert.traveler_id == traveler_id,
        EmergencyAlert.idempotency_key == alert_in.idempotency_key
    )
    result = await db.execute(stmt)
    existing_alert = result.scalar_one_or_none()
    
    if existing_alert:
        # Verify logical payload matches (we'll do a simple check on trigger_source and message)
        if existing_alert.trigger_source != alert_in.trigger_source or existing_alert.message != alert_in.message:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key reused with different payload")
        return existing_alert

    db_alert = EmergencyAlert(
        traveler_id=traveler_id,
        status="TRIGGERED",
        trigger_source=alert_in.trigger_source,
        message=alert_in.message,
        latitude=alert_in.latitude,
        longitude=alert_in.longitude,
        location_shared=alert_in.location_shared,
        delivery_status="PENDING",
        idempotency_key=alert_in.idempotency_key
    )
    db.add(db_alert)
    
    try:
        await db.commit()
        await db.refresh(db_alert)
    except IntegrityError:
        # Race condition fallback
        await db.rollback()
        result = await db.execute(stmt)
        existing_alert = result.scalar_one_or_none()
        if existing_alert:
            if existing_alert.trigger_source != alert_in.trigger_source or existing_alert.message != alert_in.message:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key reused with different payload")
            return existing_alert
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Idempotency constraint failed unexpectedly")

    # Dispatch via Adapter
    mode = os.environ.get("EMERGENCY_ALERT_MODE", "in_app").lower()
    
    if mode == "webhook":
        adapter = WebhookEmergencyAlertAdapter()
    elif mode == "hybrid":
        # Usually both, but for now just webhook
        adapter = WebhookEmergencyAlertAdapter()
    else:
        adapter = InAppEmergencyAlertAdapter()

    dispatched = await adapter.dispatch(db_alert.id, alert_in, traveler_id)
    
    if dispatched:
        db_alert.status = "DISPATCHED"
        db_alert.delivery_status = "DELIVERED"
    else:
        db_alert.status = "FAILED"
        db_alert.delivery_status = "FAILED"
        
    await db.commit()
    await db.refresh(db_alert)
    return db_alert

async def get_emergency_alerts(db: AsyncSession, traveler_id: str) -> List[EmergencyAlert]:
    stmt = select(EmergencyAlert).where(
        EmergencyAlert.traveler_id == traveler_id
    ).order_by(EmergencyAlert.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_emergency_alert(db: AsyncSession, traveler_id: str, alert_id: str) -> EmergencyAlert:
    stmt = select(EmergencyAlert).where(
        EmergencyAlert.traveler_id == traveler_id,
        EmergencyAlert.id == alert_id
    )
    result = await db.execute(stmt)
    db_alert = result.scalar_one_or_none()
    if not db_alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return db_alert

async def cancel_emergency_alert(db: AsyncSession, traveler_id: str, alert_id: str) -> EmergencyAlert:
    db_alert = await get_emergency_alert(db, traveler_id, alert_id)
    
    if db_alert.status in ["CANCELLED", "FAILED"]:
        return db_alert
        
    db_alert.status = "CANCELLED"
    db_alert.cancelled_at = datetime.now(UTC)
    
    await db.commit()
    await db.refresh(db_alert)
    return db_alert

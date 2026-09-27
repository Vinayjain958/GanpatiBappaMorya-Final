from typing import Protocol
import httpx
import os
import logging
from src.schemas.safety import EmergencyAlertCreate

logger = logging.getLogger(__name__)

class EmergencyAlertAdapter(Protocol):
    async def dispatch(self, alert_id: str, alert_data: EmergencyAlertCreate, traveler_id: str) -> bool:
        ...

class InAppEmergencyAlertAdapter:
    async def dispatch(self, alert_id: str, alert_data: EmergencyAlertCreate, traveler_id: str) -> bool:
        # In-app delivery just succeeds deterministically if everything is valid
        logger.info(f"InApp delivery dispatched for alert {alert_id} for traveler {traveler_id}")
        return True

class WebhookEmergencyAlertAdapter:
    async def dispatch(self, alert_id: str, alert_data: EmergencyAlertCreate, traveler_id: str) -> bool:
        webhook_url = os.environ.get("SAFETY_WEBHOOK_URL")
        if not webhook_url:
            logger.error("SAFETY_WEBHOOK_URL not configured")
            return False
            
        # Basic SSRF protection - don't allow local/private IPs ideally, but for now we just restrict to configured URL
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                payload = {
                    "alert_id": alert_id,
                    "traveler_id": traveler_id,
                    "trigger_source": alert_data.trigger_source,
                    "message": alert_data.message,
                    "latitude": alert_data.latitude,
                    "longitude": alert_data.longitude
                }
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Webhook dispatch failed: {e}")
            return False

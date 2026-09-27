from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException, status
from typing import List

from src.models.safety import EmergencyContact
from src.schemas.safety import EmergencyContactCreate, EmergencyContactUpdate

async def get_emergency_contacts(db: AsyncSession, traveler_id: str) -> List[EmergencyContact]:
    stmt = select(EmergencyContact).where(
        EmergencyContact.traveler_id == traveler_id
    ).order_by(EmergencyContact.priority.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def create_emergency_contact(db: AsyncSession, traveler_id: str, contact_in: EmergencyContactCreate) -> EmergencyContact:
    if contact_in.is_primary:
        # Unset primary on others
        await _unset_other_primaries(db, traveler_id)

    db_contact = EmergencyContact(
        traveler_id=traveler_id,
        name=contact_in.name,
        phone=contact_in.phone,
        relationship=contact_in.relationship,
        priority=contact_in.priority,
        is_primary=contact_in.is_primary,
        is_active=contact_in.is_active
    )
    db.add(db_contact)
    await db.commit()
    await db.refresh(db_contact)
    return db_contact

async def update_emergency_contact(db: AsyncSession, traveler_id: str, contact_id: str, contact_in: EmergencyContactUpdate) -> EmergencyContact:
    db_contact = await _get_contact_or_404(db, traveler_id, contact_id)

    update_data = contact_in.model_dump(exclude_unset=True)
    if update_data.get("is_primary"):
        await _unset_other_primaries(db, traveler_id, exclude_id=contact_id)

    for key, value in update_data.items():
        setattr(db_contact, key, value)

    await db.commit()
    await db.refresh(db_contact)
    return db_contact

async def delete_emergency_contact(db: AsyncSession, traveler_id: str, contact_id: str) -> None:
    db_contact = await _get_contact_or_404(db, traveler_id, contact_id)
    await db.delete(db_contact)
    await db.commit()

async def _get_contact_or_404(db: AsyncSession, traveler_id: str, contact_id: str) -> EmergencyContact:
    stmt = select(EmergencyContact).where(
        EmergencyContact.traveler_id == traveler_id,
        EmergencyContact.id == contact_id
    )
    result = await db.execute(stmt)
    db_contact = result.scalar_one_or_none()
    if not db_contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency contact not found")
    return db_contact

async def _unset_other_primaries(db: AsyncSession, traveler_id: str, exclude_id: str | None = None) -> None:
    stmt = update(EmergencyContact).where(
        EmergencyContact.traveler_id == traveler_id,
        EmergencyContact.is_primary == True
    ).values(is_primary=False)
    
    if exclude_id:
        stmt = stmt.where(EmergencyContact.id != exclude_id)
        
    await db.execute(stmt)

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import User, UserDevice
from ..models.schemas import ApiResponse, DeviceDeactivateRequest, DeviceRegistrationRequest
from .shared import api_response, get_current_user

DEVICE_TAG = "2] User Management"

router = APIRouter(tags=[DEVICE_TAG])


def _device_to_schema(device: UserDevice) -> dict:
    return {
        "id": device.id,
        "userId": device.user_id,
        "platform": device.platform,
        "deviceName": device.device_name,
        "isActive": device.is_active,
        "createdAt": device.created_at,
        "updatedAt": device.updated_at,
        "lastUsedAt": device.last_used_at,
    }


@router.post("/devices/register", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def register_device(
    payload: DeviceRegistrationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = payload.token.strip()
    platform = payload.platform.strip().lower()
    device_name = payload.deviceName.strip() if payload.deviceName else None

    device = db.query(UserDevice).filter(UserDevice.device_token == token).first()
    now = datetime.now(timezone.utc)
    created = device is None
    if not device:
        device = UserDevice(
            user_id=current_user.id,
            device_token=token,
            platform=platform,
            device_name=device_name,
            is_active=True,
            last_used_at=now,
        )
        db.add(device)
    else:
        device.user_id = current_user.id
        device.platform = platform
        device.device_name = device_name
        device.is_active = True
        device.last_used_at = now

    db.commit()
    db.refresh(device)
    return api_response("Device registered", {"created": created, "device": _device_to_schema(device)})


@router.delete("/devices/token", response_model=ApiResponse)
def deactivate_device(
    payload: DeviceDeactivateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.query(UserDevice).filter(
        UserDevice.user_id == current_user.id,
        UserDevice.device_token == payload.token.strip(),
    ).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device token not found")

    device.is_active = False
    device.last_used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(device)
    return api_response("Device deactivated", _device_to_schema(device))

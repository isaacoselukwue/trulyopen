from __future__ import annotations

import logging

from fastapi import APIRouter

from app.schemas import HardwareInfo
from app.services import hardware

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/hardware")
def get_hardware() -> HardwareInfo:
    return hardware.get_hardware_info()

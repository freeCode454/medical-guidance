"""v1 接口路由聚合。"""
from fastapi import APIRouter

from app.api.v1 import auth, doctor, kb, patient, ws_ticket

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(patient.router)
api_v1_router.include_router(doctor.router)
api_v1_router.include_router(kb.router)
api_v1_router.include_router(ws_ticket.router)

__all__ = ["api_v1_router"]

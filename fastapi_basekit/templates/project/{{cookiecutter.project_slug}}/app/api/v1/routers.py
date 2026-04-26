"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import auth_router
from app.api.v1.endpoints.user import user_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(user_router, tags=["Users"])

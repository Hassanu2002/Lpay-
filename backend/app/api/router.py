from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.kyc import router as kyc_router
from app.api.routes.payments import router as payments_router
from app.api.routes.webhooks import router as webhooks_router
from app.api.routes.wallet import router as wallet_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, tags=["authentication"])
api_router.include_router(kyc_router, tags=["kyc"])
api_router.include_router(payments_router, tags=["payments"])
api_router.include_router(webhooks_router, tags=["webhooks"])
api_router.include_router(wallet_router, tags=["wallet"])

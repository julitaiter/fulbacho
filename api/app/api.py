from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.groups.router import router as groups_router
from app.modules.guest.router import router as guest_router
from app.modules.matches.router import router as matches_router
from app.modules.players.router import router as players_router
from app.modules.stats.router import router as stats_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(groups_router)
api_router.include_router(players_router)
api_router.include_router(matches_router)
api_router.include_router(stats_router)
api_router.include_router(guest_router)
